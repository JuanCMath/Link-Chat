import 'dart:async';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/file_transfer.dart';
import '../models/peer.dart';
import '../services/file_transfer_service.dart';
import '../state/chat_provider.dart';
import '../state/peers_provider.dart';
import 'widgets/format_bytes.dart';
import 'widgets/message_bubble.dart';

class ChatScreen extends StatefulWidget {
  final String peerId;
  const ChatScreen({super.key, required this.peerId});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  StreamSubscription<FileTransfer>? _offerSub;
  final Set<String> _promptedOffers = {};

  @override
  void initState() {
    super.initState();
    context.read<ChatProvider>().loadHistory(widget.peerId);

    _offerSub = context.read<FileTransferService>().updates.listen((t) {
      if (t.peerId != widget.peerId) return;
      if (t.direction != TransferDirection.receive) return;
      if (t.status != TransferStatus.offering) return;
      if (!_promptedOffers.add(t.sid)) return;
      _promptAcceptOffer(t);
    });
  }

  Future<void> _promptAcceptOffer(FileTransfer t) async {
    if (!mounted) return;
    final accept = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Archivo entrante'),
        content: Text('${t.fileName} (${formatBytes(t.size)})'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Rechazar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Aceptar'),
          ),
        ],
      ),
    );
    if (!mounted) return;
    await context.read<FileTransferService>().respondToOffer(t.sid, accept ?? false);
  }

  Future<void> _pickAndSendFile(Peer peer) async {
    final result = await FilePicker.platform.pickFiles();
    final path = result?.files.single.path;
    if (path == null) return;
    if (!mounted) return;
    await context.read<FileTransferService>().offerFile(peer, File(path));
  }

  void _send(Peer peer) {
    final text = _textController.text.trim();
    if (text.isEmpty) return;
    context.read<ChatProvider>().sendMessage(peer, text);
    _textController.clear();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });
  }

  @override
  void dispose() {
    _offerSub?.cancel();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final peer = context.watch<PeersProvider>().byId(widget.peerId);
    final messages = context.watch<ChatProvider>().messagesFor(widget.peerId);

    return Scaffold(
      appBar: AppBar(
        title: Text(peer?.name ?? 'Fuera de línea'),
        bottom: peer == null
            ? const PreferredSize(
                preferredSize: Size.fromHeight(24),
                child: Padding(
                  padding: EdgeInsets.only(bottom: 6),
                  child: Text('Este dispositivo ya no está en la red',
                      style: TextStyle(fontSize: 12)),
                ),
              )
            : null,
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(12),
              itemCount: messages.length,
              itemBuilder: (context, i) => MessageBubble(message: messages[i]),
            ),
          ),
          StreamBuilder<FileTransfer>(
            stream: context.read<FileTransferService>().updates,
            builder: (context, snapshot) {
              final t = snapshot.data;
              if (t == null ||
                  t.peerId != widget.peerId ||
                  t.status != TransferStatus.transferring) {
                return const SizedBox.shrink();
              }
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${t.direction == TransferDirection.send ? "Enviando" : "Recibiendo"} ${t.fileName}',
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                    LinearProgressIndicator(value: t.progress),
                  ],
                ),
              );
            },
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.attach_file),
                    onPressed: peer == null ? null : () => _pickAndSendFile(peer),
                  ),
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      enabled: peer != null,
                      decoration: const InputDecoration(hintText: 'Mensaje...'),
                      onSubmitted: (_) => peer == null ? null : _send(peer),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.send),
                    onPressed: peer == null ? null : () => _send(peer),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
