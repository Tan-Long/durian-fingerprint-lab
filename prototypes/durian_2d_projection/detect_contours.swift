// PROTOTYPE: expose Apple Vision contours as JSON for RGB spike-foot detection.
import Foundation
import Vision

guard CommandLine.arguments.count >= 2 else {
    fatalError("usage: detect_contours IMAGE [CONTRAST]")
}

let request = VNDetectContoursRequest()
request.contrastAdjustment = Float(CommandLine.arguments.dropFirst(2).first ?? "1.5")!
request.detectsDarkOnLight = true
request.maximumImageDimension = 1920
let handler = VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1]))
try handler.perform([request])
guard let observation = request.results?.first else {
    print("[]")
    exit(0)
}

var output: [[[Float]]] = []
for index in 0..<observation.contourCount {
    let contour = try observation.contour(at: index)
    if contour.pointCount >= 8 {
        output.append(contour.normalizedPoints.map { [$0.x, $0.y] })
    }
}
let data = try JSONSerialization.data(withJSONObject: output)
FileHandle.standardOutput.write(data)
