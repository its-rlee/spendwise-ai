import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../services/spendwise_api.dart';
import 'document_review_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final ImagePicker _picker = ImagePicker();

  static const ink = Color(0xFF112624);
  static const lime = Color(0xFFCBF575);

  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();

    // Open the camera automatically when this screen appears.
    // On web, keep the import option instead.
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _capture();
      });
    }
  }

  Future<void> _capture({bool fromGallery = false}) async {
    if (_busy) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final photo = await _picker.pickImage(
        source: fromGallery ? ImageSource.gallery : ImageSource.camera,
        maxWidth: 2400,
        maxHeight: 3200,
        imageQuality: 88,
      );

      if (!mounted || photo == null) return;

      final filename = photo.name.toLowerCase();

      if (!filename.endsWith('.jpg') &&
          !filename.endsWith('.jpeg') &&
          !filename.endsWith('.png')) {
        throw ApiException(415, 'Please use a JPG or PNG receipt photo.');
      }

      final Uint8List bytes = await photo.readAsBytes();

      if (bytes.isEmpty || bytes.length > SpendwiseApi.maxDocumentBytes) {
        throw ApiException(413, 'The receipt image must be under 5 MB.');
      }

      if (!mounted) return;

      setState(() => _busy = false);

      // Pass the photo into the existing Gemini workflow.
      final action = await Navigator.push<String>(
        context,
        MaterialPageRoute(
          builder: (_) => DocumentReviewScreen(
            initialReceiptBytes: bytes,
            initialReceiptFilename: photo.name,
          ),
        ),
      );

      if (!mounted) return;

      if (action == 'dashboard') {
        Navigator.pop(context);
      } else if (action == 'scan') {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _capture();
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = error is ApiException
              ? error.message
              : 'Could not open or read the receipt photo.';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ink,
      appBar: AppBar(
        backgroundColor: ink,
        foregroundColor: Colors.white,
        title: const Text(
          'spendwise.',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  const SizedBox(height: 24),
                  const Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Ready to\nscan?',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 42,
                        height: 1.08,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -1.5,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Capture your receipt. Let AI handle the details.',
                      style: TextStyle(color: Color(0xFFB8CDCA), fontSize: 16),
                    ),
                  ),
                  const Spacer(),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 250),
                    child: _busy
                        ? const Column(
                            key: ValueKey('busy'),
                            children: [
                              CircularProgressIndicator(color: lime),
                              SizedBox(height: 20),
                              Text(
                                'Opening camera...',
                                style: TextStyle(color: Colors.white),
                              ),
                            ],
                          )
                        : Container(
                            key: const ValueKey('ready'),
                            width: double.infinity,
                            padding: const EdgeInsets.symmetric(
                              vertical: 56,
                              horizontal: 20,
                            ),
                            decoration: BoxDecoration(
                              color: const Color(0xFF1C3633),
                              borderRadius: BorderRadius.circular(28),
                              border: Border.all(
                                color: const Color(0xFF53716B),
                                width: 1.5,
                              ),
                            ),
                            child: const Column(
                              children: [
                                Icon(
                                  Icons.receipt_long_rounded,
                                  color: lime,
                                  size: 96,
                                ),
                                SizedBox(height: 18),
                                Text(
                                  'Your next receipt goes here',
                                  textAlign: TextAlign.center,
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 18,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                  ),
                  const Spacer(),
                  if (_error != null) ...[
                    Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Color(0xFFFFAB99)),
                    ),
                    const SizedBox(height: 12),
                  ],
                  SizedBox(
                    width: double.infinity,
                    height: 58,
                    child: FilledButton.icon(
                      onPressed: _busy ? null : () => _capture(),
                      style: FilledButton.styleFrom(
                        backgroundColor: lime,
                        foregroundColor: ink,
                      ),
                      icon: const Icon(Icons.camera_alt_rounded),
                      label: const Text(
                        'Scan receipt',
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextButton.icon(
                    onPressed: _busy ? null : () => _capture(fromGallery: true),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Import existing photo'),
                    style: TextButton.styleFrom(foregroundColor: Colors.white),
                  ),
                  TextButton(
                    onPressed: _busy ? null : () => Navigator.pop(context),
                    child: const Text('Go to dashboard'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
