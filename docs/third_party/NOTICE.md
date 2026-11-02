MiniFASNet architecture, detector and preprocessing provenance: MinivisionAI, Silent-Face-Anti-Spoofing, https://github.com/minivision-ai/Silent-Face-Anti-Spoofing, Apache-2.0. Original scripts identify author zhuying, Minivision, 2020. Our local detector/crop implementation follows the published computation.

ONNX export weights and inference reference: yakhyo/face-anti-spoofing, https://github.com/yakhyo/face-anti-spoofing, Apache-2.0. We use one V2 ONNX model rather than the original two-model ensemble, and reject absent/multiple faces rather than silently selecting the highest-confidence detection. We keep the official boundary-shift crop rather than the simplified ONNX clipping.

Model weights and original images are downloaded separately, never embedded in the handoff archive. Retained third-party license texts apply to their respective upstream materials. Public media provenance and supplier terms are recorded in data/source_manifest.json and docs/data_card.md.
