import 'dart:io';

/// A peer discovered on the local network via UDP beacons.
class Peer {
  final String id;
  final String name;
  final InternetAddress address;
  final int tcpPort;
  final DateTime lastSeen;

  const Peer({
    required this.id,
    required this.name,
    required this.address,
    required this.tcpPort,
    required this.lastSeen,
  });

  Peer copyWith({
    String? name,
    InternetAddress? address,
    int? tcpPort,
    DateTime? lastSeen,
  }) {
    return Peer(
      id: id,
      name: name ?? this.name,
      address: address ?? this.address,
      tcpPort: tcpPort ?? this.tcpPort,
      lastSeen: lastSeen ?? this.lastSeen,
    );
  }

  bool get isStale =>
      DateTime.now().difference(lastSeen) > const Duration(seconds: 15);
}
