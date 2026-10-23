import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../services/spendwise_api.dart';
import '../theme/terminal_theme.dart';
import 'document_review_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> with WidgetsBindingObserver {
  final _picker = ImagePicker();
  CameraController? _controller;
  List<CameraDescription> _cameras = [];
  CameraDescription? _selected;
  bool _opening = false;
  bool _busy = false;
  bool _leaving = false;
  String? _error;

  bool get _ready => _controller?.value.isInitialized == true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Browser camera permissions often need a direct user interaction;
    // native Android may initialize automatically.
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _openCamera();
      });
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (kIsWeb) return;
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      _releaseCamera();
    }
    if (state == AppLifecycleState.resumed && !_busy && !_opening) {
      _openCamera();
    }
  }

  Future<void> _releaseCamera() async {
    final old = _controller;
    _controller = null;
    if (mounted) setState(() {});
    await old?.dispose();
  }

  Future<void> _openCamera({CameraDescription? device}) async {
    if (_opening || _busy || _ready) return;
    setState(() { _opening = true; _error = null; });
    CameraController? next;
    try {
      final available = await availableCameras();
      if (available.isEmpty) {
        throw StateError('No camera detected');
      }
      final selected = device ?? available.firstWhere(
        (camera) => camera.lensDirection == CameraLensDirection.back,
        orElse: () => available.first,
      );
      next = CameraController(
        selected,
        ResolutionPreset.high,
        enableAudio: false,
      );
      await next.initialize();
      if (!mounted) {
        await next.dispose();
        return;
      }
      _cameras = available;
      _selected = selected;
      final previous = _controller;
      setState(() => _controller = next);
      await previous?.dispose();
    } catch (_) {
      await next?.dispose();
      if (mounted) {
        setState(() {
          _error = 'Camera access unavailable. Allow permission in your '
              'browser/device settings, or import a photo.';
        });
      }
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  Future<void> _switchCamera() async {
    if (_busy || _opening || _cameras.length < 2) return;
    final currentIndex = _cameras.indexWhere(
      (camera) => camera.name == _selected?.name,
    );
    final next = _cameras[(currentIndex + 1) % _cameras.length];
    await _releaseCamera();
    if (mounted) await _openCamera(device: next);
  }

  Future<void> _capture({bool importPhoto = false}) async {
    if (_busy || _opening) return;
    setState(() { _busy = true; _error = null; });
    try {
      final XFile? photo;
      if (importPhoto) {
        photo = await _picker.pickImage(
          source: ImageSource.gallery,
          maxWidth: 2400, maxHeight: 3200, imageQuality: 88,
        );
      } else {
        if (!_ready || _controller == null) {
          throw StateError('Camera not ready');
        }
        photo = await _controller!.takePicture();
      }
      if (photo == null || !mounted) return;

      final Uint8List bytes = await photo.readAsBytes();
      if (bytes.isEmpty || bytes.length > SpendwiseApi.maxDocumentBytes) {
        throw ApiException(413, 'Image exceeds 5 MB. Import a smaller photo.');
      }
      final filename = importPhoto
          ? photo.name
          : 'receipt_${DateTime.now().millisecondsSinceEpoch}.jpg';
      if (!filename.toLowerCase().endsWith('.jpg') &&
          !filename.toLowerCase().endsWith('.jpeg') &&
          !filename.toLowerCase().endsWith('.png')) {
        throw ApiException(415, 'Use a JPEG or PNG receipt photo.');
      }
      await _releaseCamera();
      if (!mounted) return;
      final action = await Navigator.push<String>(
        context,
        MaterialPageRoute(
          builder: (_) => DocumentReviewScreen(
            initialReceiptBytes: bytes,
            initialReceiptFilename: filename,
          ),
        ),
      );
      if (!mounted) return;
      if (action == 'dashboard') {
        _leaving = true;
        Navigator.pop(context);
        return;
      }
    } catch (error) {
      if (mounted) {
        setState(() => _error = error is ApiException
            ? error.message
            : 'Capture unsuccessful. Try another photo.');
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        if (!_leaving && !_ready) _openCamera();
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  Widget _cameraView() {
    return Container(
      height: 390,
      width: double.infinity,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: TerminalColors.background,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: TerminalColors.soft),
      ),
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (_ready)
            Center(child: CameraPreview(_controller!))
          else
            Center(child: _opening
                ? const TerminalLoading(label: 'CAMERA INITIALIZING')
                : const Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.center_focus_strong, size: 78,
                          color: TerminalColors.soft),
                      SizedBox(height: 18),
                      Text('CAMERA STANDBY',
                          style: TextStyle(
                            letterSpacing: 2,
                            color: TerminalColors.phosphor,
                          )),
                    ],
                  )),
          const Positioned.fill(child: _ScanSweep()),
          IgnorePointer(
            child: Center(
              child: FractionallySizedBox(
                widthFactor: 0.83, heightFactor: 0.78,
                child: Container(
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: TerminalColors.phosphor.withValues(alpha: 0.6),
                      width: 1.4,
                    ),
                    borderRadius: BorderRadius.circular(7),
                  ),
                  child: const Center(
                    child: Icon(Icons.add, color: TerminalColors.phosphor,
                        size: 18),
                  ),
                ),
              ),
            ),
          ),
          const Positioned(
            top: 17, left: 16,
            child: Text('SCAN / OPTICAL INPUT',
                style: TextStyle(color: TerminalColors.phosphor,
                    fontSize: 10, letterSpacing: 1.5)),
          ),
          const Positioned(
            bottom: 16, left: 16,
            child: Text('ALIGN ALL RECEIPT EDGES',
                style: TextStyle(color: TerminalColors.phosphor,
                    fontSize: 10, letterSpacing: 1.5)),
          ),
        ],
      ),
    );
  }

  Widget _controls() {
    return TerminalPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const TerminalSectionTitle('Optical scanner', index: '02'),
          const SizedBox(height: 14),
          const Text(
            'Keep the entire receipt in frame. '
            'Sharp text and even lighting improve AI extraction.',
            style: TextStyle(color: TerminalColors.muted, height: 1.6),
          ),
          const SizedBox(height: 20),
          if (_error != null) ...[
            Text(_error!, style: const TextStyle(color: TerminalColors.danger)),
            const SizedBox(height: 15),
          ],
          if (!_ready && !_opening)
            TerminalActionButton(
              label: 'Activate live camera',
              icon: Icons.videocam_outlined,
              onPressed: _busy ? null : _openCamera,
            )
          else
            TerminalActionButton(
              label: 'Capture receipt',
              icon: Icons.camera_alt_rounded,
              onPressed: _ready && !_busy ? () => _capture() : null,
              busy: _busy,
            ),
          const SizedBox(height: 12),
          TerminalActionButton(
            label: 'Import existing image',
            icon: Icons.photo_library_outlined,
            onPressed: _busy ? null : () => _capture(importPhoto: true),
            primary: false,
          ),
          if (_cameras.length > 1) ...[
            const SizedBox(height: 9),
            TextButton.icon(
              onPressed: _busy ? null : _switchCamera,
              icon: const Icon(Icons.flip_camera_android_outlined),
              label: const Text('Switch camera'),
            ),
          ],
          const SizedBox(height: 18),
          const Text('PIPELINE STATUS', style: TextStyle(
            color: TerminalColors.amber, fontSize: 11, letterSpacing: 1.5,
          )),
          const SizedBox(height: 8),
          const Text(
            '01  IMAGE CAPTURE\n02  PRIVATE UPLOAD\n'
            '03  GEMINI EXTRACTION\n04  HUMAN VERIFICATION',
            style: TextStyle(
              color: TerminalColors.soft, fontSize: 11, height: 2,
            ),
          ),
          const SizedBox(height: 15),
          TextButton.icon(
            onPressed: _busy ? null : () => Navigator.pop(context),
            icon: const Icon(Icons.dashboard_outlined),
            label: const Text('Return to dashboard'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const TerminalLogo(size: 39),
      ),
      body: SafeArea(
        child: LayoutBuilder(builder: (context, constraints) {
          final wide = constraints.maxWidth >= 880;
          return SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 17, 20, 36),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1100),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const TerminalSectionTitle('Field acquisition', index: '01'),
                    const SizedBox(height: 12),
                    const Text('SCAN A RECEIPT.',
                        style: TextStyle(
                          fontSize: 30, color: TerminalColors.phosphor,
                          fontWeight: FontWeight.w900, letterSpacing: -1,
                        )),
                    const SizedBox(height: 21),
                    if (wide)
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 3, child: _cameraView()),
                          const SizedBox(width: 20),
                          Expanded(flex: 2, child: _controls()),
                        ],
                      )
                    else ...[
                      _cameraView(),
                      const SizedBox(height: 18),
                      _controls(),
                    ],
                  ],
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}

class _ScanSweep extends StatefulWidget {
  const _ScanSweep();

  @override
  State<_ScanSweep> createState() => _ScanSweepState();
}

class _ScanSweepState extends State<_ScanSweep>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animation = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2600),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.of(context).disableAnimations) {
      _animation.stop();
    } else if (!_animation.isAnimating) {
      _animation.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _animation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: ExcludeSemantics(
        child: RepaintBoundary(
          child: AnimatedBuilder(
            animation: _animation,
            builder: (context, child) => Align(
              alignment: Alignment(0, -0.87 + _animation.value * 1.74),
              child: Container(
                height: 2,
                margin: const EdgeInsets.symmetric(horizontal: 24),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Colors.transparent,
                      TerminalColors.phosphor.withValues(alpha: 0.5),
                      Colors.transparent,
                    ],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: TerminalColors.phosphor.withValues(alpha: 0.25),
                      blurRadius: 16,
                      spreadRadius: 2,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
