import 'dart:async';
import 'dart:typed_data';

/// A single framed unit exchanged over a [PeerConnection]'s TCP stream.
class Frame {
  final int type;
  final Uint8List payload;
  const Frame(this.type, this.payload);
}

/// Wire format: `[4 bytes length BE][1 byte type][payload]`.
///
/// TCP is a byte stream, not a message stream, so unlike the raw-Ethernet
/// version of LinkChat (where each `recv()` already returned one frame) we
/// need explicit length-prefixing to know where one frame ends and the next
/// begins. No CRC/bit-stuffing is needed here: TCP already guarantees
/// ordered, error-checked, complete delivery of every byte.
class FrameCodec {
  static Uint8List encode(int type, List<int> payload) {
    final out = Uint8List(4 + 1 + payload.length);
    final length = 1 + payload.length;
    out[0] = (length >> 24) & 0xFF;
    out[1] = (length >> 16) & 0xFF;
    out[2] = (length >> 8) & 0xFF;
    out[3] = length & 0xFF;
    out[4] = type & 0xFF;
    out.setRange(5, out.length, payload);
    return out;
  }
}

/// Reassembles frames out of arbitrarily-chunked bytes coming off a socket.
class FrameDecoder {
  final StreamController<Frame> _controller = StreamController<Frame>();
  Uint8List _buf = Uint8List(0);

  Stream<Frame> get frames => _controller.stream;

  void add(Uint8List chunk) {
    if (_buf.isEmpty) {
      _buf = chunk;
    } else {
      final merged = Uint8List(_buf.length + chunk.length)
        ..setRange(0, _buf.length, _buf)
        ..setRange(_buf.length, _buf.length + chunk.length, chunk);
      _buf = merged;
    }
    _drain();
  }

  void _drain() {
    var offset = 0;
    while (_buf.length - offset >= 4) {
      final len = ByteData.sublistView(_buf, offset, offset + 4)
          .getUint32(0, Endian.big);
      if (_buf.length - offset - 4 < len) break; // frame not fully buffered
      if (len < 1) {
        offset += 4 + len; // malformed empty frame, skip defensively
        continue;
      }
      final start = offset + 4;
      final type = _buf[start];
      final payload = Uint8List.fromList(_buf.sublist(start + 1, start + len));
      _controller.add(Frame(type, payload));
      offset = start + len;
    }
    if (offset > 0) {
      _buf = Uint8List.fromList(_buf.sublist(offset));
    }
  }

  void close() => _controller.close();
}
