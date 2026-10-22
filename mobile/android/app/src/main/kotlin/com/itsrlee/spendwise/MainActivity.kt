package com.itsrlee.spendwise

import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import android.util.AtomicFile
import androidx.exifinterface.media.ExifInterface
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {
    private var pending: MethodChannel.Result? = null
    private var exportText: String? = null
    private val disk = Executors.newSingleThreadExecutor()
    private val receiptDir by lazy { File(filesDir, "receipts").apply { mkdirs() } }
    private val stateFile by lazy { AtomicFile(File(filesDir, "receipts.json")) }
    private val recognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "spendwise/local")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "load" -> onDisk(result) {
                        if (stateFile.baseFile.exists()) stateFile.openRead().bufferedReader().use { it.readText() } else null
                    }
                    "save" -> onDisk(result) {
                        val json = call.argument<String>("json") ?: error("Missing data")
                        require(json.length <= 20_000_000) { "Receipt storage is full. Export and remove older receipts." }
                        require(JSONObject(json).getInt("version") == 1)
                        val stream = stateFile.startWrite()
                        try { stream.write(json.toByteArray(Charsets.UTF_8)); stateFile.finishWrite(stream) }
                        catch (e: Exception) { stateFile.failWrite(stream); throw e }
                        null
                    }
                    "imagePath" -> result.success(receiptDir.absolutePath)
                    "deleteImage" -> onDisk(result) {
                        val name = call.argument<String>("name") ?: ""
                        require(Regex("[a-f0-9-]+\\.jpg").matches(name))
                        File(receiptDir, name).delete()
                    }
                    "scan", "import", "export" -> {
                        if (pending != null) { result.error("BUSY", "Finish the current scan first.", null); return@setMethodCallHandler }
                        pending = result
                        try {
                            when (call.method) {
                                "scan" -> startScanner()
                                "import" -> startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                                    type = "image/*"; addCategory(Intent.CATEGORY_OPENABLE)
                                }, 202)
                                else -> {
                                    exportText = call.argument<String>("json")
                                    startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                                        type = "application/json"; addCategory(Intent.CATEGORY_OPENABLE)
                                        putExtra(Intent.EXTRA_TITLE, "spendwise-receipts.json")
                                    }, 203)
                                }
                            }
                        } catch (e: Exception) { fail("Could not open this feature. Try importing an image.") }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun onDisk(result: MethodChannel.Result, work: () -> Any?) {
        disk.execute {
            try { val value = work(); runOnUiThread { result.success(value) } }
            catch (e: Exception) { runOnUiThread { result.error("STORAGE", "Could not read or save receipts. Free up storage and retry.", null) } }
        }
    }

    private fun startScanner() {
        val options = GmsDocumentScannerOptions.Builder()
            .setGalleryImportAllowed(true).setPageLimit(1)
            .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_JPEG)
            .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_FULL).build()
        GmsDocumentScanning.getClient(options).getStartScanIntent(this)
            .addOnSuccessListener {
                try { startIntentSenderForResult(it, 201, null, 0, 0, 0) }
                catch (e: Exception) { fail("Scanner unavailable. Use Import photo instead.") }
            }
            .addOnFailureListener { fail("Scanner needs Google Play services and an initial download. Connect once, or use Import photo.") }
    }

    @Deprecated("Activity result bridge for FlutterActivity")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode !in 201..203 || pending == null) return
        if (resultCode != Activity.RESULT_OK) { finish(null); return }
        if (requestCode == 203) {
            val uri = data?.data ?: run { fail("No export location selected."); return }
            val text = exportText ?: run { fail("No receipts to export."); return }
            disk.execute {
                try {
                    (contentResolver.openOutputStream(uri) ?: error("No destination")).use { it.write(text.toByteArray(Charsets.UTF_8)) }
                    runOnUiThread { finish(true) }
                } catch (e: Exception) { runOnUiThread { fail("Could not export receipts.") } }
            }
            return
        }
        val uri = if (requestCode == 201) GmsDocumentScanningResult.fromActivityResultIntent(data)?.pages?.firstOrNull()?.imageUri else data?.data
        if (uri == null) { fail("No receipt image received."); return }
        recognize(uri)
    }

    private fun recognize(uri: Uri) {
        disk.execute {
            var saved: File? = null
            try {
                // Bound decoded memory, correct EXIF, and retain enough pixels for small receipt text.
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
                require(bounds.outWidth > 0 && bounds.outHeight > 0)
                var sample = 1
                while (maxOf(bounds.outWidth, bounds.outHeight) / sample > 3200) sample *= 2
                val bitmap = contentResolver.openInputStream(uri)?.use {
                    BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
                } ?: error("Unreadable image")
                val exif = contentResolver.openInputStream(uri)?.use { ExifInterface(it) }
                val matrix = Matrix().apply {
                    if (exif?.isFlipped == true) postScale(-1f, 1f)
                    postRotate((exif?.rotationDegrees ?: 0).toFloat())
                }
                val corrected = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
                val file = File(receiptDir, "${UUID.randomUUID()}.jpg")
                saved = file
                file.outputStream().use { corrected.compress(Bitmap.CompressFormat.JPEG, 95, it) }
                if (corrected !== bitmap) bitmap.recycle()
                val input = InputImage.fromBitmap(corrected, 0)
                runOnUiThread {
                    recognizer.process(input)
                        .addOnSuccessListener { text ->
                            val lines = text.textBlocks.flatMap { it.lines }.map { line ->
                                val box = line.boundingBox
                                mapOf("text" to line.text, "left" to (box?.left ?: 0),
                                    "top" to (box?.top ?: 0), "right" to (box?.right ?: 0), "bottom" to (box?.bottom ?: 0))
                            }
                            finish(mapOf("text" to text.text, "lines" to lines, "imageName" to file.name))
                        }
                        .addOnFailureListener { file.delete(); fail("Could not read the image. Try a brighter, sharper photo.") }
                        .addOnCompleteListener { corrected.recycle() }
                }
            } catch (e: Exception) { saved?.delete(); runOnUiThread { fail("This image could not be opened. Try a JPG or PNG photo.") } }
        }
    }

    private fun finish(value: Any?) { val reply = pending; pending = null; exportText = null; reply?.success(value) }
    private fun fail(message: String) { val reply = pending; pending = null; exportText = null; reply?.error("SCAN", message, null) }
}
