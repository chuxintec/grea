using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Grea.Foundation.Contracts;

namespace Grea.Foundation.Runtime
{
    // Single writer, trusted application-owned root. Payload is an opaque versioned DTO.
    public sealed class FileSaveStore : ISaveStore
    {
        const int MaxBytes = 1024 * 1024;
        readonly string path;
        public FileSaveStore(string root, string playerNamespace, string qaNamespace, bool qa)
        {
            Check(playerNamespace); Check(qaNamespace);
            if (string.Equals(playerNamespace, qaNamespace, StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("QA namespace must differ from player namespace");
            if (!Path.IsPathRooted(root)) throw new ArgumentException("Save root must be absolute");
            path = Path.Combine(root, qa ? qaNamespace : playerNamespace, "save.v1");
        }
        static void Check(string value)
        {
            if (value == null || !Regex.IsMatch(value, @"\A[a-z][a-z0-9-]{0,47}\z") ||
                Regex.IsMatch(value, @"\A(con|prn|aux|nul|com[0-9]|lpt[0-9])\z"))
                throw new ArgumentException("Invalid save namespace");
        }
        static string Hash(byte[] bytes)
        { using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant(); }
        static string Decode(string file)
        {
            if (new FileInfo(file).Length > MaxBytes + 128) throw new InvalidDataException("Save exceeds budget");
            var text = File.ReadAllText(file, new UTF8Encoding(false, true));
            var parts = text.Split(new[] { '\n' }, 3);
            if (parts.Length != 3 || parts[0] != "grea-save:1" || parts[1] != Hash(Encoding.UTF8.GetBytes(parts[2])))
                throw new InvalidDataException("Save version or checksum mismatch; original preserved");
            return parts[2];
        }
        public string Read() => File.Exists(path) ? Decode(path) : null;
        // Recovery is explicit and read-only; never silently overwrite a damaged save.
        public string ReadBackup() => File.Exists(path + ".backup") ? Decode(path + ".backup") : null;
        static bool Valid(string file)
        {
            if (!File.Exists(file)) return false;
            try { Decode(file); return true; }
            catch (InvalidDataException) { return false; }
            catch (DecoderFallbackException) { return false; }
        }
        static void Quarantine(string file)
        { File.Move(file, file + ".corrupt-" + Guid.NewGuid().ToString("N")); }
        // Explicit application decision; never invoked implicitly by Read/Write.
        // A checksum-valid pending write takes precedence over the previous main save.
        public string Recover()
        {
            var pending = path + ".pending";
            if (File.Exists(pending))
            {
                if (Valid(pending))
                {
                    if (File.Exists(path) && !Valid(path)) Quarantine(path);
                    if (File.Exists(path)) File.Replace(pending, path, path + ".backup");
                    else File.Move(pending, path);
                    return "pending-committed";
                }
                Quarantine(pending);
            }
            if (!File.Exists(path)) return "empty";
            if (Valid(path)) return "main-preserved";
            var backup = path + ".backup";
            if (!Valid(backup)) throw new InvalidDataException("No valid recovery copy; damaged main preserved");
            File.Copy(backup, pending, false);
            Decode(pending);
            Quarantine(path);
            File.Move(pending, path);
            return "backup-restored";
        }
        public void Write(string value)
        {
            if (value == null) throw new ArgumentNullException(nameof(value));
            var bytes = new UTF8Encoding(false, true).GetBytes(value);
            if (bytes.Length > MaxBytes) throw new ArgumentException("Save exceeds budget");
            if (File.Exists(path)) Decode(path); // Corrupt/unknown originals require explicit recovery.
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var temp = path + ".pending";
            // A previous interruption is surfaced, never deleted implicitly.
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                var envelope = Encoding.UTF8.GetBytes("grea-save:1\n" + Hash(bytes) + "\n" + value);
                stream.Write(envelope, 0, envelope.Length); stream.Flush(true);
            }
            Decode(temp);
            if (File.Exists(path)) File.Replace(temp, path, path + ".backup");
            else File.Move(temp, path);
        }
    }
}
