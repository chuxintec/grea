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
