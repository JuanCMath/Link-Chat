import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/peer.dart';
import '../network/discovery_service.dart';

/// Live, sorted list of peers currently visible on the network.
class PeersProvider extends ChangeNotifier {
  final DiscoveryService discovery;
  List<Peer> _peers = const [];
  StreamSubscription<List<Peer>>? _sub;

  PeersProvider(this.discovery) {
    _sub = discovery.peers.listen((peers) {
      _peers = [...peers]
        ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
      notifyListeners();
    });
  }

  List<Peer> get peers => _peers;

  Peer? byId(String id) {
    for (final peer in _peers) {
      if (peer.id == id) return peer;
    }
    return null;
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
