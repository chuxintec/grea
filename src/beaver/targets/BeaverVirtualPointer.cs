// Test-only, in-process Unity Input System virtual pointer companion.
// It has no native cursor, window activation, OS-event injection, Editor, or game-state path.
#if BEAVER_VIRTUAL_POINTER && ENABLE_INPUT_SYSTEM
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Layouts;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.InputSystem.UI;
using UnityEngine.SceneManagement;

namespace Beaver.VirtualPointer
{
    [InputControlLayout(canRunInBackground = true)]
    public sealed class BeaverVirtualMouse : Mouse
    {
        // Deliberately do not call Mouse.MakeCurrent: preserve physical Mouse.current.
        public override void MakeCurrent() { }
    }

    [DefaultExecutionOrder(32000)]
    public sealed class BeaverVirtualPointer : MonoBehaviour
    {
        const int MaxLineBytes = 65536;
        const string CommandContract = "beaver-virtual-pointer-command/1";
        const string ReceiptContract = "beaver-virtual-pointer-receipt/1";
        static readonly string[] RequestKeys = { "schemaVersion", "contract", "backend", "channelId", "token", "operation", "instanceId", "deviceId", "sequence", "expiresUnixMs", "coordinateSpace", "screenWidth", "screenHeight", "x", "y", "scrollX", "scrollY", "points", "stepFrames" };
        static readonly HashSet<string> Operations = new HashSet<string> { "hello", "inspect", "move", "down", "up", "click", "drag", "scroll", "release", "stop", "capture" };

        [Serializable] sealed class Config
        {
            public int schemaVersion;
            public string contract, channelId, token, endpointPath, receiptRoot, projectId, buildId, profileId, unityVersion, inputSystemVersion;
            public int leaseSeconds, idleReleaseSeconds, commandMaxSeconds;
            public bool stopOnTakeover;
        }
        sealed class Pending
        {
            public Dictionary<string, object> Request;
            public AutoResetEvent Done = new AutoResetEvent(false);
            public Dictionary<string, object> Receipt;
            public volatile bool Disconnected;
            public volatile string AbortReason;
            public bool AbortHandled;
        }
        sealed class Route
        {
            public InputSystemUIInputModule Module;
            public InputActionReference OldPoint, OldClick, OldMiddleClick, OldRightClick, OldScroll, OldMove, OldSubmit, OldCancel, OldTrackedOrientation, OldTrackedPosition;
            public InputActionReference NewPoint, NewClick, NewMiddleClick, NewRightClick, NewScroll, NewMove, NewSubmit, NewCancel, NewTrackedOrientation, NewTrackedPosition;
            public bool[] OldEnabled;
        }

        static BeaverVirtualPointer instance;
        Config config;
        TcpListener listener;
        Thread acceptThread;
        readonly object queueLock = new object();
        readonly Queue<Pending> pending = new Queue<Pending>();
        readonly List<Route> routes = new List<Route>();
        InputActionAsset virtualActionsAsset;
        BeaverVirtualMouse device;
        string instanceId, deviceId, buildGuid, endpointNonce, coordinateSpace = "unity-screen-pixels";
        string endpointFile;
        int screenWidth, screenHeight;
        long lastAccepted, framesQueued, framesConsumed, inputEventsQueued, ackFrame, lastEventFrame;
        long lastCommandSequence;
        string lastCommandState = "none";
        Dictionary<string, object> lastCommandReceipt;
        long lastActivityTicks;
        bool isDown, plannedDown, stopping, stopReserved, cleanupDone, physicalTakeover;
        Vector2 devicePosition, plannedPosition;
        volatile bool alive;
        volatile bool listenerFailed;
        bool shutdownAfterRelease;
        bool safetyReleasePending, safetyReleaseAwaitingAck;
        int safetyReleaseEventFrame;
        Pending active;
        Queue<MouseState> eventSteps = new Queue<MouseState>();
        string activeOperation;
        string activeErrorCode;
        long activeSequence;
        int eventCountForActive;
        bool backgroundBefore;
        bool backgroundChanged;
        int lastQueuedUnityFrame = -1;
        string runtimeUnityVersion, runtimeInputSystemVersion;
        volatile bool runtimeFocused, runtimeBatchMode;
        int processId, osFrontmostPid = -1;
        int frontmostRefreshFrame = -1;
        bool osFrontmostAvailable, listenerStarted, endpointPublished, deviceCreated, configPathsValidated, shutdownLifecycleWritten;
        string shutdownReason;
        int terminalScreenWidth, terminalScreenHeight, terminalUiRouteCount;
        bool terminalDeviceRemoved, terminalActionsRestored, terminalListenerStopped, terminalEndpointRemoved, terminalBackgroundRestored;
        IntPtr nsWorkspaceClass, sharedWorkspaceSelector, frontmostApplicationSelector, processIdentifierSelector;

#if UNITY_STANDALONE_OSX
        [DllImport("/usr/lib/libobjc.A.dylib", EntryPoint = "objc_getClass", CallingConvention = CallingConvention.Cdecl)]
        static extern IntPtr ObjcGetClass(string name);
        [DllImport("/usr/lib/libobjc.A.dylib", EntryPoint = "sel_registerName", CallingConvention = CallingConvention.Cdecl)]
        static extern IntPtr SelRegisterName(string name);
        [DllImport("/usr/lib/libobjc.A.dylib", EntryPoint = "objc_msgSend", CallingConvention = CallingConvention.Cdecl)]
        static extern IntPtr ObjcSendId(IntPtr receiver, IntPtr selector);
        [DllImport("/usr/lib/libobjc.A.dylib", EntryPoint = "objc_msgSend", CallingConvention = CallingConvention.Cdecl)]
        static extern int ObjcSendInt(IntPtr receiver, IntPtr selector);
#endif

        /// <summary>True while the explicitly enabled companion owns its virtual Input System device.</summary>
        public static bool IsActive { get { return instance != null && instance.alive && instance.device != null && instance.device.added; } }

        /// <summary>Input System device id for source-specific UI integrations, or -1 when inactive.</summary>
        public static int DeviceId { get { return IsActive ? instance.device.deviceId : -1; } }

        /// <summary>Tests the device attached to an Input System UI pointer event without consulting Mouse.current.</summary>
        public static bool IsVirtualPointerEvent(PointerEventData data)
        {
            var extended = data as ExtendedPointerEventData;
            return IsActive && extended != null && object.ReferenceEquals(extended.device, instance.device);
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Bootstrap()
        {
            if (!Debug.isDebugBuild || Application.isEditor) return;
            string path = Environment.GetEnvironmentVariable("BEAVER_VIRTUAL_POINTER_CONFIG");
            if (String.IsNullOrEmpty(path)) return;
            if (Application.platform != RuntimePlatform.OSXPlayer)
            {
                Debug.LogWarning("BEAVER_VIRTUAL_POINTER_NOT_SUPPORTED_PLATFORM");
                return;
            }
            try
            {
                var go = new GameObject("Beaver Virtual Pointer QA Companion");
                DontDestroyOnLoad(go);
                instance = go.AddComponent<BeaverVirtualPointer>();
                instance.backgroundBefore = Application.runInBackground;
                instance.backgroundChanged = true;
                Application.runInBackground = true;
                instance.StartCoroutine(instance.InitializeAtStableViewport(path));
            }
            catch (Exception e)
            {
                try { if (instance != null) instance.Shutdown("initialization_failure"); } catch { }
                Debug.LogError("Beaver virtual pointer initialization failed: " + e.GetType().Name);
            }
        }

        IEnumerator InitializeAtStableViewport(string path)
        {
            try { LoadConfiguration(path); }
            catch (Exception e)
            {
                try { Shutdown(e is NotSupportedException ? "not_supported_frontmost_observer" : "configuration_invalid"); } catch { }
                Debug.LogError("Beaver virtual pointer initialization failed: " + e.GetType().Name);
                yield break;
            }
            int previousWidth = -1, previousHeight = -1, stableFrames = 0;
            for (int frame = 0; frame < 120 && stableFrames < 2; frame++)
            {
                yield return null;
                runtimeFocused = Application.isFocused;
                runtimeBatchMode = Application.isBatchMode;
                RefreshFrontmostPid();
                int width = Screen.width, height = Screen.height;
                if (width > 0 && height > 0 && width == previousWidth && height == previousHeight) stableFrames++;
                else stableFrames = 0;
                previousWidth = width; previousHeight = height;
            }
            if (stableFrames < 2)
            {
                Shutdown("viewport_unavailable"); yield break;
            }
            if (!osFrontmostAvailable || osFrontmostPid <= 0)
            {
                Shutdown("not_supported_frontmost_observer"); yield break;
            }
            try { Initialize(path); }
            catch (Exception e)
            {
                try { Shutdown("initialization_failure"); } catch { }
                Debug.LogError("Beaver virtual pointer initialization failed: " + e.GetType().Name);
            }
        }

        void Initialize(string path)
        {
            if (instance != this) throw new InvalidOperationException("Companion already exists");
            if (config == null) LoadConfiguration(path);
            SetupRuntime();
        }

        void LoadConfiguration(string path)
        {
            if (path.Length > 4096 || !File.Exists(path)) throw new InvalidDataException("Explicit configuration file is unavailable");
            byte[] bytes = File.ReadAllBytes(path);
            if (bytes.Length == 0 || bytes.Length > 16384) throw new InvalidDataException("Configuration size is invalid");
            var root = Json.Parse(StrictUtf8(bytes)) as Dictionary<string, object>;
            RequireKeys(root, new[] { "schemaVersion", "contract", "channelId", "token", "endpointPath", "receiptRoot", "projectId", "buildId", "profileId", "unityVersion", "inputSystemVersion", "leaseSeconds", "idleReleaseSeconds", "commandMaxSeconds", "stopOnTakeover" });
            config = new Config { schemaVersion = Int(root, "schemaVersion"), contract = Str(root, "contract"), channelId = Str(root, "channelId"), token = Str(root, "token"), endpointPath = Str(root, "endpointPath"), receiptRoot = Str(root, "receiptRoot"), projectId = Str(root, "projectId"), buildId = Str(root, "buildId"), profileId = Str(root, "profileId"), unityVersion = Str(root, "unityVersion"), inputSystemVersion = Str(root, "inputSystemVersion"), leaseSeconds = Int(root, "leaseSeconds"), idleReleaseSeconds = Int(root, "idleReleaseSeconds"), commandMaxSeconds = Int(root, "commandMaxSeconds"), stopOnTakeover = Bool(root, "stopOnTakeover") };
            runtimeUnityVersion = Application.unityVersion;
            runtimeInputSystemVersion = InputSystemVersion();
            runtimeFocused = Application.isFocused;
            runtimeBatchMode = Application.isBatchMode;
            processId = System.Diagnostics.Process.GetCurrentProcess().Id;
            InitializeFrontmostObserver();
            ValidateConfig();
            Directory.CreateDirectory(config.receiptRoot);
            var info = new DirectoryInfo(config.receiptRoot);
            if ((info.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidDataException("Receipt root cannot be a link");
            configPathsValidated = true;
            if (!osFrontmostAvailable || osFrontmostPid <= 0) throw new NotSupportedException("Read-only OS frontmost process observation is unavailable");
        }

        void SetupRuntime()
        {
            instanceId = Guid.NewGuid().ToString("N"); endpointNonce = Hex(RandomBytes(16));
            buildGuid = ReadBuildGuid(); screenWidth = Screen.width; screenHeight = Screen.height;
            if (screenWidth < 1 || screenHeight < 1) throw new InvalidOperationException("Screen coordinate space is unavailable");
            InputSystem.RegisterLayout<BeaverVirtualMouse>(name: "BeaverVirtualMouse");
            device = InputSystem.AddDevice<BeaverVirtualMouse>();
            if (device == null) throw new InvalidOperationException("Virtual device creation failed");
            deviceCreated = true;
            deviceId = device.deviceId.ToString(CultureInfo.InvariantCulture);
            InputSystem.onBeforeUpdate += BeforeInputUpdate;
            InputSystem.onEvent += ObservePhysicalMouse;
            SceneManager.sceneLoaded += SceneLoaded;
            BindRoutes();
            listener = new TcpListener(IPAddress.Loopback, 0); listener.Start(8); listenerStarted = true;
            alive = true; lastActivityTicks = DateTime.UtcNow.Ticks;
            WriteDiscovery(((IPEndPoint)listener.LocalEndpoint).Port);
            endpointPublished = true;
            acceptThread = new Thread(AcceptLoop) { IsBackground = true, Name = "Beaver Virtual Pointer Loopback" }; acceptThread.Start();
        }

        void ValidateConfig()
        {
            if (config.schemaVersion != 1 || config.contract != "beaver-virtual-pointer-config/1" || !HexId(config.channelId, 32) || !HexId(config.token, 64) || config.leaseSeconds < 30 || config.leaseSeconds > 1800 || config.idleReleaseSeconds < 1 || config.idleReleaseSeconds > 60 || config.commandMaxSeconds < 1 || config.commandMaxSeconds > 30 || !config.stopOnTakeover || config.unityVersion != runtimeUnityVersion || config.inputSystemVersion != runtimeInputSystemVersion)
                throw new InvalidDataException("Configuration values are invalid");
            if (String.IsNullOrEmpty(config.endpointPath) || String.IsNullOrEmpty(config.receiptRoot) || String.IsNullOrEmpty(config.projectId) || String.IsNullOrEmpty(config.buildId) || String.IsNullOrEmpty(config.profileId)) throw new InvalidDataException("Configuration identity is incomplete");
            string root = Path.GetFullPath(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Library", "Application Support", "beaver", "virtual-pointer", "channels", config.channelId));
            string endpoint = Path.GetFullPath(config.endpointPath); string receipts = Path.GetFullPath(config.receiptRoot);
            if (!endpoint.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal) || !receipts.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal)) throw new InvalidDataException("Private paths are outside the channel root");
        }

        static string ReadBuildGuid()
        {
            try { return Application.buildGUID; } catch { return "unknown"; }
        }
        static bool HexId(string s, int len) { if (s == null || s.Length != len) return false; for (int i = 0; i < s.Length; i++) if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f'))) return false; return true; }
        static byte[] RandomBytes(int count) { var b = new byte[count]; using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(b); return b; }
        static string Hex(byte[] b) { var s = new StringBuilder(b.Length * 2); foreach (byte x in b) s.Append(x.ToString("x2")); return s.ToString(); }

        void WriteDiscovery(int port)
        {
            endpointFile = config.endpointPath;
            Directory.CreateDirectory(Path.GetDirectoryName(endpointFile));
            if (File.Exists(endpointFile)) throw new IOException("Endpoint path already exists");
            var d = new Dictionary<string, object> { { "schemaVersion", 1 }, { "backend", "unity-inputsystem-virtual-pointer/1" }, { "channelId", config.channelId }, { "host", "127.0.0.1" }, { "port", port }, { "pid", processId }, { "instanceId", instanceId }, { "nonce", endpointNonce }, { "buildGUID", buildGuid }, { "deviceId", deviceId }, { "unityVersion", runtimeUnityVersion }, { "inputSystemVersion", runtimeInputSystemVersion }, { "coordinateSpace", coordinateSpace }, { "screenWidth", screenWidth }, { "screenHeight", screenHeight } };
            AtomicWrite(endpointFile, Json.Write(d));
        }

        static string InputSystemVersion() { return InputSystem.version == null ? "unknown" : InputSystem.version.ToString(); }
        void InitializeFrontmostObserver()
        {
            osFrontmostPid = -1; osFrontmostAvailable = false;
#if UNITY_STANDALONE_OSX
            try
            {
                nsWorkspaceClass = ObjcGetClass("NSWorkspace");
                sharedWorkspaceSelector = SelRegisterName("sharedWorkspace");
                frontmostApplicationSelector = SelRegisterName("frontmostApplication");
                processIdentifierSelector = SelRegisterName("processIdentifier");
                osFrontmostAvailable = nsWorkspaceClass != IntPtr.Zero && sharedWorkspaceSelector != IntPtr.Zero && frontmostApplicationSelector != IntPtr.Zero && processIdentifierSelector != IntPtr.Zero;
                RefreshFrontmostPid();
            }
            catch { osFrontmostAvailable = false; osFrontmostPid = -1; }
#endif
        }
        void RefreshFrontmostPid()
        {
#if UNITY_STANDALONE_OSX
            if (!osFrontmostAvailable) { osFrontmostPid = -1; return; }
            if (frontmostRefreshFrame == Time.frameCount) return;
            frontmostRefreshFrame = Time.frameCount;
            try
            {
                IntPtr workspace = ObjcSendId(nsWorkspaceClass, sharedWorkspaceSelector);
                IntPtr application = workspace == IntPtr.Zero ? IntPtr.Zero : ObjcSendId(workspace, frontmostApplicationSelector);
                osFrontmostPid = application == IntPtr.Zero ? -1 : ObjcSendInt(application, processIdentifierSelector);
            }
            catch { osFrontmostAvailable = false; osFrontmostPid = -1; }
#endif
        }
        static bool HasActualStateChange(InputEventPtr evt, InputDevice source)
        {
            try { foreach (var control in evt.EnumerateChangedControls(source, 0.0001f)) if (control != null) return true; }
            catch { }
            return false;
        }
        static void AtomicWrite(string path, string content) { string tmp = path + ".tmp-" + Guid.NewGuid().ToString("N"); File.WriteAllText(tmp, content, new UTF8Encoding(false)); if (File.Exists(path)) throw new IOException("Owned output path changed"); File.Move(tmp, path); }

        void AcceptLoop()
        {
            while (alive)
            {
                TcpClient client = null;
                try { client = listener.AcceptTcpClient(); client.ReceiveTimeout = 2000; client.SendTimeout = 2000; client.NoDelay = true; ThreadPool.QueueUserWorkItem(_ => HandleClient(client)); }
                catch (SocketException) { if (alive) listenerFailed = true; }
                catch (ObjectDisposedException) { break; }
                catch { if (client != null) client.Close(); if (alive) listenerFailed = true; }
            }
        }

        void HandleClient(TcpClient client)
        {
            using (client)
            using (var stream = client.GetStream())
            {
                try
                {
                    byte[] line = ReadLine(stream, MaxLineBytes);
                    var req = Json.Parse(StrictUtf8(line)) as Dictionary<string, object>;
                    ValidateRequestShape(req);
                    string op = Str(req, "operation");
                    if (!ConstantTimeEquals(Str(req, "token"), config.token) || Str(req, "channelId") != config.channelId || Int(req, "schemaVersion") != 1 || Str(req, "contract") != CommandContract || Str(req, "backend") != "unity-inputsystem-virtual-pointer/1") throw new RequestException("AUTH_OR_CONTRACT");
                    if (op == "hello" || op == "inspect")
                    {
                        if (Long(req, "sequence") != 0) throw new RequestException("INSPECT_SEQUENCE_INVALID");
                        if (op == "hello")
                        {
                            bool hasInstance = req.ContainsKey("instanceId"), hasDevice = req.ContainsKey("deviceId");
                            if (hasInstance != hasDevice) throw new RequestException("HELLO_IDENTITY_INCOMPLETE");
                            if (hasInstance && (Str(req, "instanceId") != instanceId || Str(req, "deviceId") != deviceId)) throw new RequestException("INSTANCE_MISMATCH");
                            if (!hasInstance && lastAccepted != 0) throw new RequestException("HELLO_BIND_ALREADY_USED");
                        }
                        if (op == "inspect" && (Str(req, "instanceId") != instanceId || Str(req, "deviceId") != deviceId)) throw new RequestException("INSTANCE_MISMATCH");
                        Send(stream, op == "hello" ? Receipt("verified", "", 0, 0) : InspectReceipt()); return;
                    }
                    ValidateIdentityAndBounds(req, op);
                    if (!alive || stopping || stopReserved) throw new RequestException("STOPPED");
                    Pending item = null;
                    lock (queueLock)
                    {
                        long seq = Long(req, "sequence");
                        if (seq != lastAccepted + 1) throw new RequestException("SEQUENCE_REJECTED");
                        if (stopReserved) throw new RequestException("STOPPED");
                        lastAccepted = seq;
                        if (op == "stop") stopReserved = true;
                        lastCommandSequence = seq;
                        lastCommandState = "pending";
                        lastCommandReceipt = Receipt("pending", "", seq, 0);
                        if (op != "capture") { item = new Pending { Request = req }; pending.Enqueue(item); }
                    }
                    if (op == "capture")
                    {
                        var receipt = Receipt("not_supported", "CAPTURE_NOT_SUPPORTED", Long(req, "sequence"), 0);
                        if (!PersistReceipt(receipt, Long(req, "sequence"))) { receipt["status"] = "partial"; receipt["errorCode"] = "RECEIPT_WRITE_FAILED"; }
                        UpdateLastCommand(receipt);
                        Send(stream, receipt); return;
                    }
                    DateTime deadline = DateTime.UtcNow.AddSeconds(config.commandMaxSeconds);
                    while (!item.Done.WaitOne(100))
                    {
                        if (client.Client.Poll(0, SelectMode.SelectRead) && client.Client.Available == 0) { item.Disconnected = true; item.AbortReason = "COMMAND_DISCONNECTED"; return; }
                        if (DateTime.UtcNow >= deadline)
                        {
                            item.AbortReason = "COMMAND_TIMEOUT";
                            DateTime cleanupDeadline = DateTime.UtcNow.AddSeconds(2);
                            while (!item.Done.WaitOne(100) && DateTime.UtcNow < cleanupDeadline)
                            {
                                if (client.Client.Poll(0, SelectMode.SelectRead) && client.Client.Available == 0) { item.Disconnected = true; item.AbortReason = "COMMAND_DISCONNECTED"; return; }
                            }
                            if (item.Receipt != null) Send(stream, item.Receipt);
                            else Send(stream, Receipt("partial", "COMMAND_OUTCOME_UNKNOWN", Long(req, "sequence"), 0));
                            return;
                        }
                    }
                    Send(stream, item.Receipt ?? Receipt("partial", "NO_RECEIPT", Long(req, "sequence"), 0));
                }
                catch (RequestException e) { try { Send(stream, Receipt("blocked", e.Code, 0, 0)); } catch { } }
                catch (Exception) { try { Send(stream, Receipt("blocked", "REQUEST_INVALID", 0, 0)); } catch { } }
            }
        }

        void ValidateRequestShape(Dictionary<string, object> r)
        {
            if (r == null) throw new RequestException("JSON_OBJECT_REQUIRED");
            foreach (var k in r.Keys) if (Array.IndexOf(RequestKeys, k) < 0) throw new RequestException("UNKNOWN_FIELD");
            foreach (var k in new[] { "schemaVersion", "contract", "backend", "channelId", "token", "operation", "sequence" }) if (!r.ContainsKey(k)) throw new RequestException("MISSING_FIELD");
            string op = Str(r, "operation"); if (!Operations.Contains(op)) throw new RequestException("UNKNOWN_OPERATION");
            var allowed = new HashSet<string>(new[] { "schemaVersion", "contract", "backend", "channelId", "token", "operation", "sequence" });
            if (op == "hello") { allowed.Add("instanceId"); allowed.Add("deviceId"); }
            else if (op == "inspect") { allowed.Add("instanceId"); allowed.Add("deviceId"); }
            else
            {
                foreach (var k in new[] { "instanceId", "deviceId", "expiresUnixMs", "coordinateSpace", "screenWidth", "screenHeight" }) allowed.Add(k);
                if (op == "move" || op == "down" || op == "up" || op == "click" || op == "drag" || op == "scroll") { allowed.Add("x"); allowed.Add("y"); }
                if (op == "drag") { allowed.Add("points"); allowed.Add("stepFrames"); }
                if (op == "scroll") { allowed.Add("scrollX"); allowed.Add("scrollY"); }
            }
            foreach (var k in r.Keys) if (!allowed.Contains(k)) throw new RequestException("FIELD_NOT_ALLOWED_FOR_OPERATION");
            if (op == "inspect" && (!r.ContainsKey("instanceId") || !r.ContainsKey("deviceId"))) throw new RequestException("MISSING_FIELD");
            if (Str(r, "token").Length > 128 || Str(r, "channelId").Length > 64 || Str(r, "operation").Length > 32) throw new RequestException("FIELD_LIMIT");
        }

        void ValidateIdentityAndBounds(Dictionary<string, object> r, string op)
        {
            if (Str(r, "instanceId") != instanceId || Str(r, "deviceId") != deviceId) throw new RequestException("INSTANCE_MISMATCH");
            if (Long(r, "sequence") < 1 || Long(r, "expiresUnixMs") < UnixMs() || Long(r, "expiresUnixMs") > UnixMs() + config.commandMaxSeconds * 1000L) throw new RequestException("EXPIRED_OR_INVALID");
            if (Str(r, "coordinateSpace") != coordinateSpace || Int(r, "screenWidth") != screenWidth || Int(r, "screenHeight") != screenHeight) throw new RequestException("COORDINATE_SPACE_STALE");
            if (op != "stop" && op != "release" && op != "capture") CheckPoint(r);
            if (op == "scroll") { float sx = Num(r, "scrollX"), sy = Num(r, "scrollY"); if (Math.Abs(sx) > 10000 || Math.Abs(sy) > 10000) throw new RequestException("SCROLL_RANGE"); }
            if (op == "drag")
            {
                var pts = r.ContainsKey("points") ? r["points"] as List<object> : null; int frames = Int(r, "stepFrames");
                if (pts == null || pts.Count < 1 || pts.Count > 128 || frames < 1 || frames > 10) throw new RequestException("DRAG_SHAPE");
                foreach (var p in pts) { var d = p as Dictionary<string, object>; if (d == null || d.Count != 2 || !d.ContainsKey("x") || !d.ContainsKey("y")) throw new RequestException("DRAG_POINT"); CheckPoint(d); }
            }
        }
        void CheckPoint(Dictionary<string, object> r) { float x = Num(r, "x"), y = Num(r, "y"); if (x < 0 || y < 0 || x >= screenWidth || y >= screenHeight) throw new RequestException("POINT_RANGE"); }

        void Update()
        {
            if (!alive) return;
            runtimeFocused = Application.isFocused;
            runtimeBatchMode = Application.isBatchMode;
            RefreshFrontmostPid();
            if (!osFrontmostAvailable || osFrontmostPid <= 0) { Shutdown("frontmost_observer_unavailable"); return; }
            if (screenWidth != Screen.width || screenHeight != Screen.height) { Shutdown("screen_resize"); return; }
            if (listenerFailed) { Shutdown("listener_failure"); return; }
            if (DateTime.UtcNow.Ticks - lastActivityTicks > TimeSpan.FromSeconds(config.leaseSeconds).Ticks) { Shutdown("lease_expired"); return; }
            if (!safetyReleasePending && !safetyReleaseAwaitingAck && DateTime.UtcNow.Ticks - lastActivityTicks > TimeSpan.FromSeconds(config.idleReleaseSeconds).Ticks && isDown) ReleaseNow();
        }

        void LateUpdate()
        {
            if (safetyReleasePending || (safetyReleaseAwaitingAck && Time.frameCount < safetyReleaseEventFrame)) return;
            if (safetyReleaseAwaitingAck && Time.frameCount >= safetyReleaseEventFrame)
            {
                safetyReleaseAwaitingAck = false; isDown = false; ackFrame = Time.frameCount; framesConsumed = framesQueued;
                if (shutdownAfterRelease)
                {
                    if (active != null) { CompleteInterrupted(active, "partial", "COMPANION_STOPPING", eventCountForActive + 1); active = null; }
                    FinalShutdown(); return;
                }
            }
            if (!alive || active == null) return;
            if (eventSteps.Count == 0)
            {
                framesConsumed = framesQueued; ackFrame = Time.frameCount;
                string op = activeOperation; long seq = activeSequence;
                var done = active; active = null;
                if (op == "stop") Shutdown("requested_stop");
                bool cancellation = activeErrorCode == "COMMAND_DISCONNECTED" || activeErrorCode == "COMMAND_TIMEOUT" || activeErrorCode == "COMMAND_EXPIRED" || activeErrorCode == "SCENE_CHANGED";
                var resultStatus = !String.IsNullOrEmpty(activeErrorCode) ? (cancellation && eventCountForActive > 0 ? "partial" : "blocked") : (op == "stop" ? "stopped" : "consumed");
                string resultError = activeErrorCode ?? "";
                if (op == "stop" && !CleanupConfirmed) { resultStatus = "partial"; resultError = "CLEANUP_INCOMPLETE"; }
                var receipt = Receipt(resultStatus, resultError, seq, eventCountForActive);
                receipt["buttonDown"] = isDown; receipt["ackFrame"] = ackFrame; receipt["lastEventFrame"] = lastEventFrame;
                if (!PersistReceipt(receipt, seq)) { receipt["status"] = "partial"; receipt["errorCode"] = "RECEIPT_WRITE_FAILED"; receipt["reason"] = "RECEIPT_WRITE_FAILED"; }
                UpdateLastCommand(receipt);
                done.Receipt = receipt; done.Done.Set();
            }
        }

        void BeforeInputUpdate()
        {
            runtimeFocused = Application.isFocused;
            runtimeBatchMode = Application.isBatchMode;
            RefreshFrontmostPid();
            if (alive && (!osFrontmostAvailable || osFrontmostPid <= 0)) Shutdown("frontmost_observer_unavailable");
            if (!alive || device == null) return;
            if (safetyReleasePending)
            {
                if (lastQueuedUnityFrame == Time.frameCount) return;
                InputSystem.QueueStateEvent(device, State(devicePosition, false, Vector2.zero));
                lastQueuedUnityFrame = Time.frameCount; lastActivityTicks = DateTime.UtcNow.Ticks;
                safetyReleasePending = false; safetyReleaseAwaitingAck = true; safetyReleaseEventFrame = Time.frameCount;
                inputEventsQueued++; framesQueued++; lastEventFrame = Time.frameCount;
                return;
            }
            if (active == null)
            {
                lock (queueLock) if (pending.Count > 0) active = pending.Dequeue();
                if (active != null) Prepare(active);
            }
            if (active != null && !active.AbortHandled)
            {
                if (active.Disconnected) CancelActiveCommand("COMMAND_DISCONNECTED");
                else if (!String.IsNullOrEmpty(active.AbortReason)) CancelActiveCommand(active.AbortReason);
                else if (Long(active.Request, "expiresUnixMs") <= UnixMs()) CancelActiveCommand("COMMAND_EXPIRED");
            }
            if (active == null || eventSteps.Count == 0 || lastQueuedUnityFrame == Time.frameCount) return;
            MouseState state = eventSteps.Dequeue();
            InputSystem.QueueStateEvent(device, state);
            lastQueuedUnityFrame = Time.frameCount;
            lastActivityTicks = DateTime.UtcNow.Ticks;
            devicePosition = state.position;
            isDown = (state.buttons & 1) != 0;
            inputEventsQueued++; eventCountForActive++; lastEventFrame = Time.frameCount; framesQueued++;
        }

        void CancelActiveCommand(string reason)
        {
            active.AbortHandled = true;
            eventSteps.Clear(); activeErrorCode = reason;
            plannedDown = false;
            if (isDown) eventSteps.Enqueue(State(devicePosition, false, Vector2.zero));
        }

        void Prepare(Pending item)
        {
            var r = item.Request; activeOperation = Str(r, "operation"); activeSequence = Long(r, "sequence"); eventCountForActive = 0;
            activeErrorCode = null;
            lastActivityTicks = DateTime.UtcNow.Ticks;
            plannedDown = isDown; plannedPosition = devicePosition;
            try { ValidateIdentityAndBounds(r, activeOperation); }
            catch (RequestException e) { activeErrorCode = e.Code; eventSteps.Enqueue(State(devicePosition, isDown, Vector2.zero)); return; }
            if (routes.Count == 0 && activeOperation != "release" && activeOperation != "stop")
            {
                activeErrorCode = "UI_ROUTE_UNAVAILABLE";
                eventSteps.Enqueue(State(devicePosition, isDown, Vector2.zero));
                return;
            }
            switch (activeOperation)
            {
                case "move": AddMove(Num(r, "x"), Num(r, "y")); break;
                case "down": AddMove(Num(r, "x"), Num(r, "y")); AddButton(true); break;
                case "up": AddMove(Num(r, "x"), Num(r, "y")); AddButton(false); break;
                case "click": AddMove(Num(r, "x"), Num(r, "y")); AddButton(true); AddButton(false); break;
                case "drag":
                    AddMove(Num(r, "x"), Num(r, "y")); AddButton(true);
                    foreach (var p in (List<object>)r["points"]) { var d = (Dictionary<string, object>)p; AddMove(Num(d, "x"), Num(d, "y")); for (int n = 1; n < Int(r, "stepFrames"); n++) eventSteps.Enqueue(State(plannedPosition, true, Vector2.zero)); }
                    AddButton(false); break;
                case "scroll": AddMove(Num(r, "x"), Num(r, "y")); eventSteps.Enqueue(State(plannedPosition, plannedDown, new Vector2(Num(r, "scrollX"), Num(r, "scrollY")))); eventSteps.Enqueue(State(plannedPosition, plannedDown, Vector2.zero)); break;
                case "release": AddButton(false); break;
                case "stop": AddButton(false); stopping = true; break;
                default: eventSteps.Enqueue(State(devicePosition, isDown, Vector2.zero)); break;
            }
            if (eventSteps.Count == 0) eventSteps.Enqueue(State(devicePosition, plannedDown, Vector2.zero));
        }
        void AddMove(float x, float y) { var next = new Vector2(x, y); eventSteps.Enqueue(State(next, plannedDown, Vector2.zero)); plannedPosition = next; }
        void AddButton(bool down) { eventSteps.Enqueue(State(plannedPosition, down, Vector2.zero)); plannedDown = down; }
        static MouseState State(Vector2 p, bool down, Vector2 scroll) { var s = new MouseState { position = p, delta = Vector2.zero, scroll = scroll }; return s.WithButton(MouseButton.Left, down); }

        void ObservePhysicalMouse(InputEventPtr evt, InputDevice source)
        {
            if (!alive || !osFrontmostAvailable || osFrontmostPid != processId || device == null || source == device || source == null || !source.native || !config.stopOnTakeover) return;
            bool userDevice = source is Mouse || source is Keyboard || source is Touchscreen || source is Gamepad || source is Joystick || source is Pen;
            if (userDevice && (evt.type == StateEvent.Type || evt.type == DeltaStateEvent.Type) && HasActualStateChange(evt, source)) { physicalTakeover = true; Shutdown("physical_takeover"); }
        }

        void SceneLoaded(Scene scene, LoadSceneMode mode)
        {
            if (active != null)
            {
                eventSteps.Clear(); activeErrorCode = "SCENE_CHANGED";
                if (isDown) ReleaseNow();
            }
            else if (isDown) ReleaseNow();
            lock (queueLock) while (pending.Count > 0) CompleteInterrupted(pending.Dequeue(), "blocked", "SCENE_CHANGED", 0);
            BindRoutes();
        }
        void BindRoutes()
        {
            if (!RestoreRoutes()) throw new InvalidOperationException("Previous virtual UI routes could not be restored");
            var modules = Resources.FindObjectsOfTypeAll<InputSystemUIInputModule>();
            bool hasModule = false;
            foreach (var module in modules) if (module != null && module.gameObject.scene.IsValid() && module.isActiveAndEnabled) { hasModule = true; break; }
            if (!hasModule || device == null) return;

            virtualActionsAsset = ScriptableObject.CreateInstance<InputActionAsset>();
            virtualActionsAsset.name = "Beaver Virtual Pointer Actions";
            var map = virtualActionsAsset.AddActionMap("BeaverVirtualPointerUI");
            map.devices = new InputDevice[] { device };
            var point = map.AddAction("Point", InputActionType.PassThrough, "<BeaverVirtualMouse>/position", expectedControlLayout: "Vector2");
            var click = map.AddAction("LeftClick", InputActionType.PassThrough, "<BeaverVirtualMouse>/leftButton", expectedControlLayout: "Button");
            var middleClick = map.AddAction("MiddleClick", InputActionType.PassThrough, "<BeaverVirtualMouse>/middleButton", expectedControlLayout: "Button");
            var rightClick = map.AddAction("RightClick", InputActionType.PassThrough, "<BeaverVirtualMouse>/rightButton", expectedControlLayout: "Button");
            var scroll = map.AddAction("Scroll", InputActionType.PassThrough, "<BeaverVirtualMouse>/scroll", expectedControlLayout: "Vector2");
            var move = map.AddAction("Move", InputActionType.PassThrough, expectedControlLayout: "Vector2");
            var submit = map.AddAction("Submit", InputActionType.Button, expectedControlLayout: "Button");
            var cancel = map.AddAction("Cancel", InputActionType.Button, expectedControlLayout: "Button");
            var trackedOrientation = map.AddAction("TrackedDeviceOrientation", InputActionType.PassThrough, expectedControlLayout: "Quaternion");
            var trackedPosition = map.AddAction("TrackedDevicePosition", InputActionType.PassThrough, expectedControlLayout: "Vector3");

            foreach (var module in modules)
            {
                if (module == null || !module.gameObject.scene.IsValid() || !module.isActiveAndEnabled) continue;
                var route = new Route
                {
                    Module = module,
                    OldPoint = module.point, OldClick = module.leftClick, OldMiddleClick = module.middleClick, OldRightClick = module.rightClick,
                    OldScroll = module.scrollWheel, OldMove = module.move, OldSubmit = module.submit, OldCancel = module.cancel,
                    OldTrackedOrientation = module.trackedDeviceOrientation, OldTrackedPosition = module.trackedDevicePosition,
                    NewPoint = InputActionReference.Create(point), NewClick = InputActionReference.Create(click), NewMiddleClick = InputActionReference.Create(middleClick), NewRightClick = InputActionReference.Create(rightClick),
                    NewScroll = InputActionReference.Create(scroll), NewMove = InputActionReference.Create(move), NewSubmit = InputActionReference.Create(submit), NewCancel = InputActionReference.Create(cancel),
                    NewTrackedOrientation = InputActionReference.Create(trackedOrientation), NewTrackedPosition = InputActionReference.Create(trackedPosition)
                };
                route.OldEnabled = new[] { IsEnabled(route.OldPoint), IsEnabled(route.OldClick), IsEnabled(route.OldMiddleClick), IsEnabled(route.OldRightClick), IsEnabled(route.OldScroll), IsEnabled(route.OldMove), IsEnabled(route.OldSubmit), IsEnabled(route.OldCancel), IsEnabled(route.OldTrackedOrientation), IsEnabled(route.OldTrackedPosition) };
                routes.Add(route);
            }
            foreach (var route in routes)
            {
                var module = route.Module;
                module.point = route.NewPoint; module.leftClick = route.NewClick; module.middleClick = route.NewMiddleClick; module.rightClick = route.NewRightClick;
                module.scrollWheel = route.NewScroll; module.move = route.NewMove; module.submit = route.NewSubmit; module.cancel = route.NewCancel;
                module.trackedDeviceOrientation = route.NewTrackedOrientation; module.trackedDevicePosition = route.NewTrackedPosition;
            }
        }
        static bool IsEnabled(InputActionReference reference) { return reference != null && reference.action != null && reference.action.enabled; }
        static void RestoreEnabled(InputActionReference reference, bool enabled)
        {
            if (reference == null || reference.action == null) return;
            if (enabled && !reference.action.enabled) reference.action.Enable();
            else if (!enabled && reference.action.enabled) reference.action.Disable();
        }
        bool RestoreRoutes()
        {
            bool restored = true;
            foreach (var r in routes)
            {
                try
                {
                if (r.Module != null)
                {
                    r.Module.point = r.OldPoint; r.Module.leftClick = r.OldClick; r.Module.middleClick = r.OldMiddleClick; r.Module.rightClick = r.OldRightClick;
                    r.Module.scrollWheel = r.OldScroll; r.Module.move = r.OldMove; r.Module.submit = r.OldSubmit; r.Module.cancel = r.OldCancel;
                    r.Module.trackedDeviceOrientation = r.OldTrackedOrientation; r.Module.trackedDevicePosition = r.OldTrackedPosition;
                    RestoreEnabled(r.OldPoint, r.OldEnabled[0]); RestoreEnabled(r.OldClick, r.OldEnabled[1]); RestoreEnabled(r.OldMiddleClick, r.OldEnabled[2]);
                    RestoreEnabled(r.OldRightClick, r.OldEnabled[3]); RestoreEnabled(r.OldScroll, r.OldEnabled[4]); RestoreEnabled(r.OldMove, r.OldEnabled[5]);
                    RestoreEnabled(r.OldSubmit, r.OldEnabled[6]); RestoreEnabled(r.OldCancel, r.OldEnabled[7]); RestoreEnabled(r.OldTrackedOrientation, r.OldEnabled[8]);
                    RestoreEnabled(r.OldTrackedPosition, r.OldEnabled[9]);
                    var actual = new[] { r.Module.point, r.Module.leftClick, r.Module.middleClick, r.Module.rightClick, r.Module.scrollWheel, r.Module.move, r.Module.submit, r.Module.cancel, r.Module.trackedDeviceOrientation, r.Module.trackedDevicePosition };
                    var expected = new[] { r.OldPoint, r.OldClick, r.OldMiddleClick, r.OldRightClick, r.OldScroll, r.OldMove, r.OldSubmit, r.OldCancel, r.OldTrackedOrientation, r.OldTrackedPosition };
                    for (int i = 0; i < actual.Length; i++) if (actual[i] != expected[i] || IsEnabled(expected[i]) != r.OldEnabled[i]) restored = false;
                }
                else restored = false;
                if (r.NewPoint != null) Destroy(r.NewPoint); if (r.NewClick != null) Destroy(r.NewClick); if (r.NewMiddleClick != null) Destroy(r.NewMiddleClick); if (r.NewRightClick != null) Destroy(r.NewRightClick);
                if (r.NewScroll != null) Destroy(r.NewScroll); if (r.NewMove != null) Destroy(r.NewMove); if (r.NewSubmit != null) Destroy(r.NewSubmit); if (r.NewCancel != null) Destroy(r.NewCancel);
                if (r.NewTrackedOrientation != null) Destroy(r.NewTrackedOrientation); if (r.NewTrackedPosition != null) Destroy(r.NewTrackedPosition);
                }
                catch { restored = false; }
            }
            routes.Clear();
            try { if (virtualActionsAsset != null) { virtualActionsAsset.Disable(); Destroy(virtualActionsAsset); virtualActionsAsset = null; } }
            catch { restored = false; }
            return restored;
        }

        bool ReleaseNow()
        {
            if (device == null) return false;
            if (safetyReleasePending || safetyReleaseAwaitingAck) return true;
            while (eventSteps.Count > 0) eventSteps.Dequeue();
            bool needsReleaseFrame = isDown || (active != null && (eventCountForActive > 0 || framesQueued > framesConsumed));
            if (needsReleaseFrame) { safetyReleasePending = true; plannedDown = false; }
            return needsReleaseFrame;
        }

        void Shutdown(string reason)
        {
            if (cleanupDone || shutdownAfterRelease) return;
            if (String.IsNullOrEmpty(shutdownReason)) shutdownReason = reason;
            stopping = true;
            bool releasePending = ReleaseNow();
            if (releasePending)
            {
                shutdownAfterRelease = true;
                try { if (listener != null) listener.Stop(); } catch { }
                if (active != null) activeErrorCode = "COMPANION_STOPPING";
                lock (queueLock) while (pending.Count > 0) CompleteInterrupted(pending.Dequeue(), "blocked", "COMPANION_STOPPING", 0);
                return;
            }
            FinalShutdown();
        }

        bool CleanupConfirmed { get { return cleanupDone && !isDown && terminalDeviceRemoved && terminalActionsRestored && terminalListenerStopped && terminalBackgroundRestored && terminalEndpointRemoved; } }

        void FinalShutdown()
        {
            if (cleanupDone) return; cleanupDone = true; alive = false; shutdownAfterRelease = false; safetyReleasePending = false; safetyReleaseAwaitingAck = false;
            terminalScreenWidth = screenWidth; terminalScreenHeight = screenHeight;
            InputSystem.onBeforeUpdate -= BeforeInputUpdate; InputSystem.onEvent -= ObservePhysicalMouse; SceneManager.sceneLoaded -= SceneLoaded;
            int routesToRestore = routes.Count; terminalUiRouteCount = 0;
            foreach (var route in routes) if (route.Module != null) terminalUiRouteCount++;
            terminalActionsRestored = RestoreRoutes() && terminalUiRouteCount == routesToRestore;
            try { if (listener != null) listener.Stop(); terminalListenerStopped = true; } catch { }
            try { if (device != null && device.added) InputSystem.RemoveDevice(device); terminalDeviceRemoved = device == null || !device.added; } catch { }
            // Restore the prior application background setting; do not change global InputSettings.
            try { if (backgroundChanged) Application.runInBackground = backgroundBefore; terminalBackgroundRestored = Application.runInBackground == backgroundBefore; } catch { }
            terminalEndpointRemoved = RemoveOwnedEndpoint();
            if (active != null) { CompleteInterrupted(active, "partial", "COMPANION_STOPPED", eventCountForActive); active = null; }
            lock (queueLock) while (pending.Count > 0) CompleteInterrupted(pending.Dequeue(), "blocked", "COMPANION_STOPPED", 0);
            PersistTerminalLifecycle();
            if (instance == this) instance = null;
            Destroy(gameObject);
        }
        bool RemoveOwnedEndpoint()
        {
            try
            {
                if (String.IsNullOrEmpty(endpointFile) || !File.Exists(endpointFile)) return false;
                var d = Json.Parse(File.ReadAllText(endpointFile, Encoding.UTF8)) as Dictionary<string, object>;
                if (d != null && d.ContainsKey("nonce") && (string)d["nonce"] == endpointNonce) { File.Delete(endpointFile); return true; }
            }
            catch { }
            return false;
        }
        void PersistTerminalLifecycle()
        {
            if (shutdownLifecycleWritten || !configPathsValidated || config == null || String.IsNullOrEmpty(config.receiptRoot)) return;
            var lifecycle = new Dictionary<string, object>
            {
                { "schemaVersion", 1 }, { "contract", "beaver-virtual-pointer-lifecycle/1" },
                { "status", (shutdownReason != null && shutdownReason.StartsWith("not_supported_", StringComparison.Ordinal)) ? "not_supported" : (shutdownReason == "viewport_unavailable" ? "blocked" : (CleanupConfirmed ? "stopped" : "partial")) },
                { "reason", shutdownReason ?? "unspecified" }, { "channelId", config.channelId }, { "instanceId", instanceId ?? "" },
                { "pid", processId }, { "physicalTakeover", physicalTakeover }, { "unityFocused", runtimeFocused },
                { "applicationBatchMode", runtimeBatchMode }, { "osForeground", osFrontmostAvailable && osFrontmostPid == processId },
                { "osFrontmostAvailable", osFrontmostAvailable }, { "osFrontmostPid", osFrontmostPid },
                { "screenWidth", terminalScreenWidth }, { "screenHeight", terminalScreenHeight },
                { "observedScreenWidth", Screen.width }, { "observedScreenHeight", Screen.height },
                { "frame", Time.frameCount }, { "framesQueued", framesQueued }, { "framesConsumed", framesConsumed },
                { "inputEventsQueued", inputEventsQueued }, { "ackFrame", ackFrame }, { "lastEventFrame", lastEventFrame },
                { "buttonDown", isDown }, { "deviceCreated", deviceCreated }, { "listenerStarted", listenerStarted },
                { "endpointPublished", endpointPublished }, { "cleanupPerformed", CleanupConfirmed },
                { "actionRoutesRestored", terminalActionsRestored }, { "uiRoutesRestored", terminalUiRouteCount },
                { "deviceRemoved", terminalDeviceRemoved }, { "listenerStopped", terminalListenerStopped },
                { "endpointRemoved", terminalEndpointRemoved }, { "backgroundRestored", terminalBackgroundRestored }
            };
            try
            {
                string suffix = String.IsNullOrEmpty(instanceId) ? processId.ToString(CultureInfo.InvariantCulture) + "-" + DateTime.UtcNow.Ticks.ToString(CultureInfo.InvariantCulture) : instanceId;
                string path = Path.Combine(config.receiptRoot, "lifecycle-" + suffix + ".json");
                byte[] bytes = new UTF8Encoding(false).GetBytes(Json.Write(lifecycle));
                using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { stream.Write(bytes, 0, bytes.Length); stream.Flush(true); }
                shutdownLifecycleWritten = true;
            }
            catch { }
        }
        void CompleteInterrupted(Pending pendingCommand, string status, string code, int eventCount)
        {
            var receipt = Receipt(status, code, Long(pendingCommand.Request, "sequence"), eventCount);
            receipt["buttonDown"] = isDown; receipt["ackFrame"] = ackFrame; receipt["lastEventFrame"] = lastEventFrame;
            if (!PersistReceipt(receipt, Long(pendingCommand.Request, "sequence"))) { receipt["status"] = "partial"; receipt["errorCode"] = "RECEIPT_WRITE_FAILED"; }
            UpdateLastCommand(receipt); pendingCommand.Receipt = receipt; pendingCommand.Done.Set();
        }
        bool PersistReceipt(Dictionary<string, object> receipt, long sequence)
        {
            if (sequence < 1) return true;
            try
            {
                string path = Path.Combine(config.receiptRoot, "receipt-" + sequence.ToString("D20", CultureInfo.InvariantCulture) + ".json");
                using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    byte[] bytes = new UTF8Encoding(false).GetBytes(Json.Write(receipt));
                    if (bytes.Length > MaxLineBytes) return false;
                    stream.Write(bytes, 0, bytes.Length); stream.Flush(true);
                }
                return true;
            }
            catch { return false; }
        }
        void OnApplicationQuit() { Shutdown("application_quit"); }
        void OnDestroy() { if (!cleanupDone && device != null) Shutdown("object_destroyed"); }

        Dictionary<string, object> Receipt(string status, string error, long seq, int eventCount)
        {
            return new Dictionary<string, object> { { "schemaVersion", 1 }, { "contract", ReceiptContract }, { "backend", "unity-inputsystem-virtual-pointer/1" }, { "status", status }, { "errorCode", error }, { "channelId", config == null ? "" : config.channelId }, { "instanceId", instanceId ?? "" }, { "pid", processId }, { "buildGUID", buildGuid ?? "unknown" }, { "unityVersion", runtimeUnityVersion ?? "unknown" }, { "inputSystemVersion", runtimeInputSystemVersion ?? "unknown" }, { "deviceId", deviceId ?? "" }, { "deviceNative", false }, { "deviceCanRunInBackground", true }, { "coordinateSpace", coordinateSpace }, { "screenWidth", screenWidth }, { "screenHeight", screenHeight }, { "focused", runtimeFocused }, { "osForeground", osFrontmostAvailable && osFrontmostPid == processId }, { "frontmostPid", osFrontmostPid }, { "applicationBatchMode", runtimeBatchMode }, { "sequence", seq }, { "lastAcceptedSequence", lastAccepted }, { "framesQueued", framesQueued }, { "framesConsumed", framesConsumed }, { "inputEventsQueued", inputEventsQueued }, { "buttonDown", isDown }, { "ackFrame", ackFrame }, { "lastEventFrame", lastEventFrame }, { "physicalTakeover", physicalTakeover }, { "cleanupPerformed", CleanupConfirmed }, { "deviceRemoved", terminalDeviceRemoved }, { "actionRoutesRestored", terminalActionsRestored }, { "listenerStopped", terminalListenerStopped }, { "backgroundRestored", terminalBackgroundRestored }, { "endpointRemoved", terminalEndpointRemoved }, { "sourceIsolation", "device-specific-ui-actions" }, { "targetRoute", "InputSystemUIInputModule" }, { "targetHitName", "" }, { "targetHitFrame", 0 }, { "capturePath", "" }, { "captureSha", "" }, { "lastCommandState", status }, { "reason", error } };
        }

        void UpdateLastCommand(Dictionary<string, object> receipt)
        {
            lock (queueLock)
            {
                long sequence = Long(receipt, "sequence");
                if (sequence < lastCommandSequence) return;
                lastCommandReceipt = new Dictionary<string, object>(receipt);
                lastCommandSequence = sequence;
                lastCommandState = Str(receipt, "status");
            }
        }

        Dictionary<string, object> InspectReceipt()
        {
            lock (queueLock)
            {
                var result = Receipt("verified", "", 0, 0);
                result["lastCommandSequence"] = lastCommandSequence;
                result["lastCommandState"] = lastCommandState;
                result["lastCommandReceipt"] = lastCommandReceipt == null ? null : new Dictionary<string, object>(lastCommandReceipt);
                result["lastAckFrame"] = lastCommandReceipt != null && lastCommandReceipt.ContainsKey("ackFrame") ? lastCommandReceipt["ackFrame"] : 0L;
                result["lastInputEventsQueued"] = lastCommandReceipt != null && lastCommandReceipt.ContainsKey("inputEventsQueued") ? lastCommandReceipt["inputEventsQueued"] : 0L;
                return result;
            }
        }

        sealed class RequestException : Exception { public readonly string Code; public RequestException(string c) { Code = c; } }
        static long UnixMs() { return (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds; }
        static bool ConstantTimeEquals(string a, string b) { if (a == null || b == null) return false; int diff = a.Length ^ b.Length; int n = Math.Min(a.Length, b.Length); for (int i = 0; i < n; i++) diff |= a[i] ^ b[i]; return diff == 0; }
        static byte[] ReadLine(NetworkStream s, int max)
        {
            using (var m = new MemoryStream()) { while (m.Length <= max) { int b = s.ReadByte(); if (b < 0) throw new EndOfStreamException(); if (b == '\n') return m.ToArray(); if (b != '\r') m.WriteByte((byte)b); } throw new InvalidDataException("Request exceeds line bound"); }
        }
        static string StrictUtf8(byte[] bytes) { return new UTF8Encoding(false, true).GetString(bytes); }
        static void Send(NetworkStream s, Dictionary<string, object> response) { byte[] b = Encoding.UTF8.GetBytes(Json.Write(response) + "\n"); if (b.Length > MaxLineBytes) throw new IOException("Receipt bound exceeded"); s.Write(b, 0, b.Length); }
        static string Str(Dictionary<string, object> d, string k) { object v; if (!d.TryGetValue(k, out v) || !(v is string)) throw new RequestException("FIELD_TYPE"); return (string)v; }
        static int Int(Dictionary<string, object> d, string k) { long v = Long(d, k); if (v < Int32.MinValue || v > Int32.MaxValue) throw new RequestException("FIELD_RANGE"); return (int)v; }
        static long Long(Dictionary<string, object> d, string k) { object v; if (!d.TryGetValue(k, out v) || !(v is long)) throw new RequestException("FIELD_TYPE"); return (long)v; }
        static bool Bool(Dictionary<string, object> d, string k) { object v; if (!d.TryGetValue(k, out v) || !(v is bool)) throw new RequestException("FIELD_TYPE"); return (bool)v; }
        static float Num(Dictionary<string, object> d, string k)
        {
            object v; if (!d.TryGetValue(k, out v)) throw new RequestException("FIELD_TYPE");
            double n;
            if (v is double) n = (double)v;
            else if (v is long) n = (long)v;
            else throw new RequestException("FIELD_TYPE");
            if (Double.IsNaN(n) || Double.IsInfinity(n) || Math.Abs(n) > Single.MaxValue) throw new RequestException("FIELD_RANGE");
            return (float)n;
        }
        static void RequireKeys(Dictionary<string, object> d, string[] exact) { if (d == null || d.Count != exact.Length) throw new InvalidDataException("Configuration fields differ from contract"); foreach (var k in exact) if (!d.ContainsKey(k)) throw new InvalidDataException("Configuration is missing a required field"); }

        static class Json
        {
            public static object Parse(string s) { CheckNesting(s); int i = 0; object v = Value(s, ref i); Space(s, ref i); if (i != s.Length) throw new InvalidDataException("Trailing JSON data"); return v; }
            static void CheckNesting(string s)
            {
                int depth = 0; bool quoted = false, escaped = false;
                for (int i = 0; i < s.Length; i++)
                {
                    char c = s[i];
                    if (quoted) { if (escaped) escaped = false; else if (c == '\\') escaped = true; else if (c == '"') quoted = false; continue; }
                    if (c == '"') { quoted = true; continue; }
                    if (c == '{' || c == '[') { if (++depth > 32) throw new InvalidDataException("JSON nesting exceeds limit"); }
                    else if (c == '}' || c == ']') { if (--depth < 0) throw new InvalidDataException("Unbalanced JSON nesting"); }
                }
                if (quoted || depth != 0) throw new InvalidDataException("Incomplete JSON document");
            }
            static void Space(string s, ref int i) { while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r' || s[i] == '\n')) i++; }
            static object Value(string s, ref int i)
            {
                Space(s, ref i); if (i >= s.Length) throw new InvalidDataException("JSON ended unexpectedly"); char c = s[i];
                if (c == '{') return Object(s, ref i); if (c == '[') return Array(s, ref i); if (c == '"') return String(s, ref i);
                if (c == 't' && Literal(s, ref i, "true")) return true; if (c == 'f' && Literal(s, ref i, "false")) return false; if (c == 'n' && Literal(s, ref i, "null")) return null;
                return Number(s, ref i);
            }
            static bool Literal(string s, ref int i, string v) { if (i + v.Length > s.Length || System.String.CompareOrdinal(s, i, v, 0, v.Length) != 0) return false; i += v.Length; return true; }
            static Dictionary<string, object> Object(string s, ref int i)
            {
                i++; var d = new Dictionary<string, object>(); Space(s, ref i); if (i < s.Length && s[i] == '}') { i++; return d; }
                while (true) { Space(s, ref i); if (i >= s.Length || s[i] != '"') throw new InvalidDataException("JSON object key expected"); string k = String(s, ref i); if (d.ContainsKey(k)) throw new InvalidDataException("Duplicate JSON key"); Space(s, ref i); if (i >= s.Length || s[i++] != ':') throw new InvalidDataException("JSON colon expected"); d.Add(k, Value(s, ref i)); Space(s, ref i); if (i >= s.Length) throw new InvalidDataException("JSON object ended unexpectedly"); char c = s[i++]; if (c == '}') break; if (c != ',') throw new InvalidDataException("JSON comma expected"); }
                return d;
            }
            static List<object> Array(string s, ref int i) { i++; var a = new List<object>(); Space(s, ref i); if (i < s.Length && s[i] == ']') { i++; return a; } while (true) { if (a.Count > 256) throw new InvalidDataException("JSON array too large"); a.Add(Value(s, ref i)); Space(s, ref i); if (i >= s.Length) throw new InvalidDataException("JSON array ended unexpectedly"); char c = s[i++]; if (c == ']') break; if (c != ',') throw new InvalidDataException("JSON comma expected"); } return a; }
            static string String(string s, ref int i)
            {
                i++; var b = new StringBuilder(); while (i < s.Length) { char c = s[i++]; if (c == '"') return b.ToString(); if (c < 32) throw new InvalidDataException("Invalid JSON string"); if (c != '\\') { b.Append(c); continue; } if (i >= s.Length) break; c = s[i++]; switch (c) { case '"': case '\\': case '/': b.Append(c); break; case 'b': b.Append('\b'); break; case 'f': b.Append('\f'); break; case 'n': b.Append('\n'); break; case 'r': b.Append('\r'); break; case 't': b.Append('\t'); break; case 'u': if (i + 4 > s.Length) throw new InvalidDataException("Bad unicode escape"); b.Append((char)Int32.Parse(s.Substring(i, 4), NumberStyles.HexNumber, CultureInfo.InvariantCulture)); i += 4; break; default: throw new InvalidDataException("Bad JSON escape"); } } throw new InvalidDataException("Unterminated JSON string");
            }
            static object Number(string s, ref int i) { int start = i; if (s[i] == '-') i++; while (i < s.Length && Char.IsDigit(s[i])) i++; bool fractional = false; if (i < s.Length && s[i] == '.') { fractional = true; i++; while (i < s.Length && Char.IsDigit(s[i])) i++; } if (i < s.Length && (s[i] == 'e' || s[i] == 'E')) { fractional = true; i++; if (i < s.Length && (s[i] == '+' || s[i] == '-')) i++; while (i < s.Length && Char.IsDigit(s[i])) i++; } string n = s.Substring(start, i - start); if (fractional) { double d; if (!Double.TryParse(n, NumberStyles.Float, CultureInfo.InvariantCulture, out d) || Double.IsNaN(d) || Double.IsInfinity(d)) throw new InvalidDataException("Invalid JSON number"); return d; } long l; if (!Int64.TryParse(n, NumberStyles.Integer, CultureInfo.InvariantCulture, out l)) throw new InvalidDataException("Invalid JSON integer"); return l; }
            public static string Write(object v) { var b = new StringBuilder(); Emit(b, v); return b.ToString(); }
            static void Emit(StringBuilder b, object v)
            {
                if (v == null) { b.Append("null"); return; } if (v is string) { Quote(b, (string)v); return; } if (v is bool) { b.Append((bool)v ? "true" : "false"); return; }
                if (v is IDictionary<string, object>) { b.Append('{'); bool first = true; foreach (var p in (IDictionary<string, object>)v) { if (!first) b.Append(','); first = false; Quote(b, p.Key); b.Append(':'); Emit(b, p.Value); } b.Append('}'); return; }
                if (v is IEnumerable && !(v is string)) { b.Append('['); bool first = true; foreach (var x in (IEnumerable)v) { if (!first) b.Append(','); first = false; Emit(b, x); } b.Append(']'); return; }
                if (v is double || v is float) { b.Append(Convert.ToDouble(v, CultureInfo.InvariantCulture).ToString("R", CultureInfo.InvariantCulture)); return; }
                b.Append(Convert.ToString(v, CultureInfo.InvariantCulture));
            }
            static void Quote(StringBuilder b, string s) { b.Append('"'); foreach (char c in s) { switch (c) { case '"': b.Append("\\\""); break; case '\\': b.Append("\\\\"); break; case '\b': b.Append("\\b"); break; case '\f': b.Append("\\f"); break; case '\n': b.Append("\\n"); break; case '\r': b.Append("\\r"); break; case '\t': b.Append("\\t"); break; default: if (c < 32) b.Append("\\u").Append(((int)c).ToString("x4")); else b.Append(c); break; } } b.Append('"'); }
        }
    }
}
#endif
