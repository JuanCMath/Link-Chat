import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'network/connection_manager.dart';
import 'network/discovery_service.dart';
import 'services/chat_repository.dart';
import 'services/file_transfer_service.dart';
import 'services/identity_service.dart';
import 'state/chat_provider.dart';
import 'state/peers_provider.dart';
import 'ui/peers_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const LinkChatApp());
}

class LinkChatApp extends StatefulWidget {
  const LinkChatApp({super.key});

  @override
  State<LinkChatApp> createState() => _LinkChatAppState();
}

class _LinkChatAppState extends State<LinkChatApp> with WidgetsBindingObserver {
  final IdentityService identity = IdentityService();
  late final ConnectionManager connections = ConnectionManager(identity: identity);
  late final DiscoveryService discovery = DiscoveryService(
    identity: identity,
    tcpPortProvider: () => connections.tcpPort,
  );
  final ChatRepository chatRepo = ChatRepository();
  late final FileTransferService fileTransfers =
      FileTransferService(connections: connections);

  late final Future<void> _ready = _bootstrap();

  Future<void> _bootstrap() async {
    await identity.load();
    await chatRepo.open();
    await connections.start();
    await discovery.start();
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // LAN sockets don't survive backgrounding reliably on iOS/Android; stop
    // discovery to avoid stale beacons and resume it once foregrounded.
    if (state == AppLifecycleState.resumed) {
      discovery.start();
    } else if (state == AppLifecycleState.paused) {
      discovery.stop();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    discovery.dispose();
    fileTransfers.dispose();
    connections.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<void>(
      future: _ready,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const MaterialApp(
            home: Scaffold(body: Center(child: CircularProgressIndicator())),
          );
        }

        return MultiProvider(
          providers: [
            ChangeNotifierProvider<IdentityService>.value(value: identity),
            Provider<ConnectionManager>.value(value: connections),
            Provider<DiscoveryService>.value(value: discovery),
            Provider<FileTransferService>.value(value: fileTransfers),
            Provider<ChatRepository>.value(value: chatRepo),
            ChangeNotifierProvider(create: (_) => PeersProvider(discovery)),
            ChangeNotifierProvider(
              create: (_) => ChatProvider(
                connections: connections,
                repo: chatRepo,
                identity: identity,
              ),
            ),
          ],
          child: MaterialApp(
            title: 'Link-Chat',
            theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
            home: const PeersScreen(),
          ),
        );
      },
    );
  }
}
