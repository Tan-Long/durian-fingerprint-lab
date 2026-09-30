// PROTOTYPE: measure the translation that aligns a floating image to a reference.
import Foundation
import Vision

guard CommandLine.arguments.count == 3 else {
    fatalError("usage: register_images REFERENCE FLOATING")
}

let request = VNTranslationalImageRegistrationRequest(
    targetedImageURL: URL(fileURLWithPath: CommandLine.arguments[1])
)
let handler = VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[2]))
try handler.perform([request])
guard let observation = request.results?.first else {
    fatalError("image registration failed")
}
print("\(observation.alignmentTransform.tx) \(observation.alignmentTransform.ty)")
