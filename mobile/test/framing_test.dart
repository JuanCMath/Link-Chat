import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:linkchat_mobile/network/framing.dart';

void main() {
  test('encodes and decodes a single frame', () async {
    final encoded = FrameCodec.encode(0x10, utf8.encode('hello'));
    final decoder = FrameDecoder();
    final future = decoder.frames.first;

    decoder.add(encoded);

    final decoded = await future;
    expect(decoded.type, 0x10);
    expect(utf8.decode(decoded.payload), 'hello');
  });

  test('reassembles a frame split across many small chunks', () async {
    final payload = List.generate(500, (i) => i % 256);
    final encoded = FrameCodec.encode(0x11, payload);
    final decoder = FrameDecoder();
    final received = <Frame>[];
    decoder.frames.listen(received.add);

    for (var i = 0; i < encoded.length; i += 7) {
      final end = (i + 7).clamp(0, encoded.length);
      decoder.add(Uint8List.fromList(encoded.sublist(i, end)));
    }
    await Future<void>.delayed(Duration.zero);

    expect(received.length, 1);
    expect(received.single.type, 0x11);
    expect(received.single.payload, payload);
  });

  test('decodes multiple frames delivered in a single chunk', () async {
    final f1 = FrameCodec.encode(1, [1, 2, 3]);
    final f2 = FrameCodec.encode(2, [4, 5]);
    final decoder = FrameDecoder();
    final received = <Frame>[];
    decoder.frames.listen(received.add);

    decoder.add(Uint8List.fromList([...f1, ...f2]));
    await Future<void>.delayed(Duration.zero);

    expect(received.length, 2);
    expect(received[0].type, 1);
    expect(received[0].payload, [1, 2, 3]);
    expect(received[1].type, 2);
    expect(received[1].payload, [4, 5]);
  });
}
