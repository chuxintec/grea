import Foundation
import CoreText
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

struct GlyphSpec: Decodable { let unicode: Int; let codepoint: String; let character: String }
struct FaceSpec: Decodable {
  let generationMode: String
  let targetFamily: String
  let targetStyleName: String
  let targetPostScriptName: String
  let targetVariationAxes: [String: Double]
  let targetSystemFontFileUrl: String
  let targetSystemFontFileSha256: String
  let sourceLabelIds: [String]
  let sourceOnly: Bool
  let fontBytesCopiedOrExported: Bool
  let fontFileDistribution: String
  let requiredGlyphs: [GlyphSpec]
}
struct Plan: Decodable {
  let schema: String
  let status: String
  let targetOS: String
  let targetOSVersion: String
  let targetOSBuild: String?
  let resolutionReceiptSha256: String
  let systemFonts: [FaceSpec]
}
struct PlacedGlyph {
  let spec: GlyphSpec
  let glyph: CGGlyph
  let bounds: CGRect
  let advance: Double
  let mask: [UInt8]
  let width: Int
  let height: Int
  var x: Int = 0
  var y: Int = 0
}

func fail(_ text: String) -> Never { fputs(text + "\n", stderr); exit(2) }
func sha256Hex(_ data: Data) -> String {
  let task = Process()
  task.executableURL = URL(fileURLWithPath: "/usr/bin/shasum")
  task.arguments = ["-a", "256"]
  let input = Pipe(), output = Pipe(), error = Pipe()
  task.standardInput = input; task.standardOutput = output; task.standardError = error
  do { try task.run() } catch { fail("cannot run shasum") }
  input.fileHandleForWriting.write(data); try? input.fileHandleForWriting.close()
  let result = output.fileHandleForReading.readDataToEndOfFile()
  task.waitUntilExit()
  guard task.terminationStatus == 0, let line = String(data: result, encoding: .utf8) else { fail("shasum failed") }
  return String(line.prefix(64))
}

func systemValue(_ args: [String]) -> String {
  let process = Process(); process.executableURL = URL(fileURLWithPath: "/usr/bin/sw_vers"); process.arguments = args
  let pipe = Pipe(); process.standardOutput = pipe
  do { try process.run() } catch { fail("sw_vers failed") }
  let data = pipe.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
  guard process.terminationStatus == 0, let value = String(data: data, encoding: .utf8) else { fail("sw_vers failed") }
  return value.trimmingCharacters(in: .whitespacesAndNewlines)
}

// Two-pass 8-neighbour chamfer distance transform. Values are in 1/3-pixel units.
func distanceTransform(_ mask: [UInt8], width: Int, height: Int, targetInside: Bool) -> [Int32] {
  let inf = Int32(1 << 26)
  var d = mask.map { ((Int($0) >= 128) == targetInside) ? Int32(0) : inf }
  if width < 2 || height < 2 { return d }
  for y in 0..<height { for x in 0..<width {
    let i = y * width + x
    if x > 0 { d[i] = min(d[i], d[i - 1] + 3) }
    if y > 0 { d[i] = min(d[i], d[i - width] + 3) }
    if x > 0 && y > 0 { d[i] = min(d[i], d[i - width - 1] + 4) }
    if x + 1 < width && y > 0 { d[i] = min(d[i], d[i - width + 1] + 4) }
  }}
  for y in stride(from: height - 1, through: 0, by: -1) { for x in stride(from: width - 1, through: 0, by: -1) {
    let i = y * width + x
    if x + 1 < width { d[i] = min(d[i], d[i + 1] + 3) }
    if y + 1 < height { d[i] = min(d[i], d[i + width] + 3) }
    if x + 1 < width && y + 1 < height { d[i] = min(d[i], d[i + width + 1] + 4) }
    if x > 0 && y + 1 < height { d[i] = min(d[i], d[i + width - 1] + 4) }
  }}
  return d
}

func sdf(_ mask: [UInt8], width: Int, height: Int, range: Double) -> [UInt8] {
  let inside = distanceTransform(mask, width: width, height: height, targetInside: true)
  let outside = distanceTransform(mask, width: width, height: height, targetInside: false)
  let scale = 3.0
  return mask.indices.map { i in
    let signed = (Double(outside[i]) - Double(inside[i])) / scale
    return UInt8(max(0, min(255, Int((128.0 + signed * (127.0 / range)).rounded()))))
  }
}

func writePNG(_ pixels: [UInt8], width: Int, height: Int, url: URL) {
  var rgba = [UInt8](repeating: 0, count: width * height * 4)
  for i in pixels.indices {
    let value = pixels[i], j = i * 4
    rgba[j] = value; rgba[j + 1] = value; rgba[j + 2] = value; rgba[j + 3] = value
  }
  let data = Data(rgba)
  guard let provider = CGDataProvider(data: data as CFData),
        let image = CGImage(width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 32,
                            bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
                            bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedLast.rawValue),
                            provider: provider, decode: nil, shouldInterpolate: false,
                            intent: .defaultIntent),
        let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil)
  else { fail("cannot construct output PNG") }
  CGImageDestinationAddImage(destination, image, nil)
  guard CGImageDestinationFinalize(destination) else { fail("cannot write output PNG") }
}

guard CommandLine.arguments.count == 3 else { fail("usage: GenerateCoreTextSdf.swift PLAN.json OUTPUT_DIR") }
let planURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let planData: Data
do { planData = try Data(contentsOf: planURL) } catch { fail("cannot read plan") }
let plan: Plan
do { plan = try JSONDecoder().decode(Plan.self, from: planData) } catch { fail("invalid plan: \(error)") }
guard plan.schema == "monkey-unity-coretext-static-sdf-plan/1", plan.status == "prepared",
      plan.targetOS == "macOS", plan.systemFonts.count == 1 else { fail("unsupported/unbounded static font plan") }
guard systemValue(["-productVersion"]) == plan.targetOSVersion,
      plan.targetOSBuild == nil || systemValue(["-buildVersion"]) == plan.targetOSBuild! else { fail("target macOS version/build drifted") }
let face = plan.systemFonts[0]
guard face.generationMode == "CoreTextRasterizedStaticSDF", face.sourceOnly,
      !face.fontBytesCopiedOrExported, face.fontFileDistribution == "none",
      face.requiredGlyphs.count > 0, face.requiredGlyphs.count <= 4096 else { fail("static glyph contract is invalid or exceeds limit") }
guard FileManager.default.fileExists(atPath: face.targetSystemFontFileUrl),
      let fontData = try? Data(contentsOf: URL(fileURLWithPath: face.targetSystemFontFileUrl), options: .mappedIfSafe),
      sha256Hex(fontData) == face.targetSystemFontFileSha256 else { fail("installed target font file SHA drifted") }

let base = CTFontCreateWithName(face.targetPostScriptName as CFString, 90, nil)
var variations: [NSNumber: NSNumber] = [:]
for (tag, value) in face.targetVariationAxes {
  guard tag.utf8.count == 4 else { fail("invalid variation axis tag") }
  var id: UInt32 = 0
  for byte in tag.utf8 { id = (id << 8) | UInt32(byte) }
  variations[NSNumber(value: id)] = NSNumber(value: value)
}
let attributes: [CFString: Any] = [kCTFontVariationAttribute: variations]
let descriptor = CTFontDescriptorCreateWithAttributes(attributes as CFDictionary)
let font = CTFontCreateCopyWithAttributes(base, 90, nil, descriptor)
guard (CTFontCopyFamilyName(font) as String) == face.targetFamily,
      (CTFontCopyName(font, kCTFontStyleNameKey) as String?) == face.targetStyleName,
      (CTFontCopyPostScriptName(font) as String) == face.targetPostScriptName else { fail("CoreText face/style identity drifted") }
let applied = CTFontCopyAttribute(font, kCTFontVariationAttribute) as? NSDictionary ?? NSDictionary()
for (tag, value) in face.targetVariationAxes {
  var id: UInt32 = 0; for byte in tag.utf8 { id = (id << 8) | UInt32(byte) }
  guard abs(((applied[NSNumber(value: id)] as? NSNumber)?.doubleValue ?? .nan) - value) < 0.01 else { fail("CoreText variation axis drifted: \(tag)") }
}

let padding = 32
var placed: [PlacedGlyph] = []
for item in face.requiredGlyphs.sorted(by: { $0.unicode < $1.unicode }) {
  guard let scalar = UnicodeScalar(item.unicode), String(scalar) == item.character,
        item.unicode <= 0xFFFF else { fail("only verified single BMP Unicode scalars are supported") }
  var unit = UniChar(item.unicode), glyph: CGGlyph = 0
  guard CTFontGetGlyphsForCharacters(font, &unit, &glyph, 1), glyph != 0 else { fail("CoreText glyph mapping failed for \(item.codepoint)") }
  var bounds = CGRect.zero
  _ = CTFontGetBoundingRectsForGlyphs(font, .horizontal, &glyph, &bounds, 1)
  var advance = CGSize.zero
  _ = CTFontGetAdvancesForGlyphs(font, .horizontal, &glyph, &advance, 1)
  let contentWidth = max(1, Int(ceil(bounds.width)))
  let contentHeight = max(1, Int(ceil(bounds.height)))
  let width = contentWidth + padding * 2, height = contentHeight + padding * 2
  var mask = [UInt8](repeating: 0, count: width * height)
  let contextOK = mask.withUnsafeMutableBytes { buffer -> Bool in
    guard let context = CGContext(data: buffer.baseAddress, width: width, height: height, bitsPerComponent: 8,
                                  bytesPerRow: width, space: CGColorSpaceCreateDeviceGray(),
                                  bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return false }
    context.setShouldAntialias(true); context.setAllowsAntialiasing(true)
    context.setFillColor(gray: 1, alpha: 1)
    let origin = CGPoint(x: CGFloat(padding) - bounds.minX, y: CGFloat(padding) - bounds.minY)
    CTFontDrawGlyphs(font, &glyph, [origin], 1, context)
    return true
  }
  guard contextOK else { fail("cannot create glyph mask") }
  placed.append(PlacedGlyph(spec: item, glyph: glyph, bounds: bounds, advance: Double(advance.width),
                            mask: mask, width: width, height: height))
}

let atlasWidth = 4096, atlasHeight = 4096, sdfRange = 32.0
var x = 0, y = 0, rowHeight = 0
let ordered = placed.indices.sorted { placed[$0].height == placed[$1].height ? placed[$0].width > placed[$1].width : placed[$0].height > placed[$1].height }
for index in ordered {
  if x + placed[index].width > atlasWidth { y += rowHeight; x = 0; rowHeight = 0 }
  guard y + placed[index].height <= atlasHeight else { fail("bounded 2048px atlas capacity exceeded") }
  placed[index].x = x; placed[index].y = y
  x += placed[index].width; rowHeight = max(rowHeight, placed[index].height)
}
var atlas = [UInt8](repeating: 0, count: atlasWidth * atlasHeight)
for glyph in placed {
  let field = sdf(glyph.mask, width: glyph.width, height: glyph.height, range: sdfRange)
  for gy in 0..<glyph.height {
    let src = gy * glyph.width, dst = (glyph.y + gy) * atlasWidth + glyph.x
    atlas.replaceSubrange(dst..<(dst + glyph.width), with: field[src..<(src + glyph.width)])
  }
}
try? FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)
let atlasURL = outputURL.appendingPathComponent("glyph-atlas.png")
writePNG(atlas, width: atlasWidth, height: atlasHeight, url: atlasURL)
let glyphRecords: [[String: Any]] = placed.sorted { $0.spec.unicode < $1.spec.unicode }.map { glyph in
  ["unicode": glyph.spec.unicode, "codepoint": glyph.spec.codepoint, "character": glyph.spec.character,
   "glyphIndex": Int(glyph.glyph), "rect": ["x": glyph.x, "y": glyph.y, "width": glyph.width, "height": glyph.height],
   "contentBounds": ["xMin": glyph.bounds.minX, "yMin": glyph.bounds.minY, "width": glyph.bounds.width, "height": glyph.bounds.height],
   "metrics": ["width": glyph.bounds.width, "height": glyph.bounds.height, "bearingX": glyph.bounds.minX,
               "bearingY": glyph.bounds.maxY, "advance": glyph.advance]]
}
let metrics: [String: Any] = [
  "schema": "monkey-coretext-static-sdf-glyph-metrics/1", "status": "generated",
  "staticPlanSha256": sha256Hex(planData),
  "generatorSourceSha256": sha256Hex((try? Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[0]))) ?? Data()),
  "targetOS": plan.targetOS, "targetOSVersion": plan.targetOSVersion, "targetOSBuild": plan.targetOSBuild as Any? ?? NSNull(),
  "resolutionReceiptSha256": plan.resolutionReceiptSha256, "family": face.targetFamily,
  "styleName": face.targetStyleName, "postScriptName": face.targetPostScriptName,
  "variationAxes": face.targetVariationAxes,
  "variationAxesCanonical": String(data: try JSONSerialization.data(withJSONObject: face.targetVariationAxes, options: [.sortedKeys]), encoding: .utf8) ?? "{}",
  "fontFileSha256": face.targetSystemFontFileSha256,
  "fontFileCopiedOrExported": false, "fontFileIncluded": false,
  "pointSize": 90, "sdfSpread": sdfRange, "glyphPadding": padding, "atlasWidth": atlasWidth, "atlasHeight": atlasHeight,
  "sourceLabelIds": face.sourceLabelIds.sorted(),
  "faceMetrics": ["unitsPerEM": Int(CTFontGetUnitsPerEm(font)), "ascentLine": CTFontGetAscent(font),
                   "descentLine": -CTFontGetDescent(font), "lineHeight": CTFontGetAscent(font) + CTFontGetDescent(font) + CTFontGetLeading(font),
                   "capLine": CTFontGetCapHeight(font), "meanLine": CTFontGetXHeight(font),
                   "underlinePosition": CTFontGetUnderlinePosition(font), "underlineThickness": CTFontGetUnderlineThickness(font)],
  "textureFormat": "RGBA32-premultiplied-distance-in-alpha",
  "atlasOrigin": "top-left", "requiredGlyphCount": glyphRecords.count, "glyphs": glyphRecords,
  "glyphScope": "only frozen source Label text scalars listed in the bound plan",
  "glyphRunShaping": "one scalar maps to one verified CoreText glyph; non-BMP and shaping sequences are rejected by this generator",
  "newCharacterBoundary": "unlisted runtime or future characters have no atlas coverage",
  "visualEquivalent": false, "playerPlatformEvidence": "not_run"
]
let metricsURL = outputURL.appendingPathComponent("glyph-metrics.json")
let metricsData = try JSONSerialization.data(withJSONObject: metrics, options: [.prettyPrinted, .sortedKeys, .fragmentsAllowed])
try metricsData.write(to: metricsURL, options: .atomic)
print("generated \(glyphRecords.count) static glyphs; atlas=\(atlasURL.path); fontFileCopiedOrExported=false")
