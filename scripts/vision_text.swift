import Foundation
import ImageIO
import Vision

func process(_ path: String) -> [String: Any] {
    let url = URL(fileURLWithPath: path)
    var record: [String: Any] = ["path": path, "width": 0, "height": 0, "texts": []]

    if let source = CGImageSourceCreateWithURL(url as CFURL, nil),
       let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any] {
        record["width"] = properties[kCGImagePropertyPixelWidth] as? Int ?? 0
        record["height"] = properties[kCGImagePropertyPixelHeight] as? Int ?? 0
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]

    do {
        try VNImageRequestHandler(url: url, options: [:]).perform([request])
        record["texts"] = (request.results ?? []).compactMap { observation in
            observation.topCandidates(1).first.map {
                ["text": $0.string, "confidence": Double($0.confidence)]
            }
        }
    } catch {
        record["error"] = error.localizedDescription
    }
    return record
}

let paths = Array(CommandLine.arguments.dropFirst())
for (index, path) in paths.enumerated() {
    autoreleasepool {
        let data = try! JSONSerialization.data(withJSONObject: process(path))
        print(String(data: data, encoding: .utf8)!)
    }
    if (index + 1) % 20 == 0 || index + 1 == paths.count {
        FileHandle.standardError.write(Data("OCR \(index + 1)/\(paths.count)\n".utf8))
    }
}
