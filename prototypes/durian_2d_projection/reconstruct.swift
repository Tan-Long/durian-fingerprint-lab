// PROTOTYPE: Apple Object Capture bridge. Delete if turntable imagery cannot reconstruct.
import Foundation
import RealityKit

@main
struct Reconstruct {
    static func main() async throws {
        guard CommandLine.arguments.count == 4 else {
            throw NSError(domain: "usage", code: 1, userInfo: [
                NSLocalizedDescriptionKey: "usage: reconstruct.swift INPUT_DIR OUTPUT.usdz reduced|medium|full"
            ])
        }
        let input = URL(fileURLWithPath: CommandLine.arguments[1])
        let output = URL(fileURLWithPath: CommandLine.arguments[2])
        let detail: PhotogrammetrySession.Request.Detail
        switch CommandLine.arguments[3] {
        case "reduced": detail = .reduced
        case "medium": detail = .medium
        case "full": detail = .full
        default: throw NSError(domain: "detail", code: 1)
        }

        var configuration = PhotogrammetrySession.Configuration()
        configuration.sampleOrdering = .unordered
        configuration.featureSensitivity = .high
        let session = try PhotogrammetrySession(input: input, configuration: configuration)
        try session.process(requests: [.modelFile(url: output, detail: detail)])

        for try await event in session.outputs {
            switch event {
            case .requestProgress(_, let progress):
                print("progress \(Int(progress * 100))%")
            case .requestComplete:
                print("model \(output.path)")
            case .requestError(_, let error):
                print("request error: \(String(reflecting: error))")
                throw error
            case .invalidSample(let id, let reason):
                print("invalid sample \(id): \(reason)")
            case .skippedSample(let id):
                print("skipped sample \(id)")
            case .processingComplete:
                return
            default:
                continue
            }
        }
    }
}
