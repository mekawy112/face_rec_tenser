import 'dart:io';
import 'dart:ui' as ui;
import 'dart:math';
import 'dart:typed_data';
import 'package:face_rec_tenser/ML/Recognition.dart';
import 'package:face_rec_tenser/ML/Recognizer.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_commons/google_mlkit_commons.dart';
import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';
import 'package:image_picker/image_picker.dart';
import 'package:image/image.dart' as img;

class RecognitionScreen extends StatefulWidget {
  const RecognitionScreen({Key? key}) : super(key: key);

  @override
  State<RecognitionScreen> createState() => _HomePageState();
}

class _HomePageState extends State<RecognitionScreen> {
  //TODO declare variables
  late ImagePicker imagePicker;
  File? _image;

  //TODO declare detector

  late FaceDetector faceDetector;

  //TODO declare face recognizer
  late Recognizer recognizer;

  ui.Image? image; // Use ui.Image type

  @override
  void initState() {
    // TODO: implement initState
    super.initState();
    imagePicker = ImagePicker();

    //TODO initialize face detector

    final options = FaceDetectorOptions(
      performanceMode: FaceDetectorMode.accurate,
    );
    faceDetector = FaceDetector(options: options);

    //TODO initialize face recognizer
    recognizer = Recognizer();
  }

  //TODO capture image using camera
  _imgFromCamera() async {
    XFile? pickedFile = await imagePicker.pickImage(source: ImageSource.camera);
    if (pickedFile != null) {
      _image = File(pickedFile.path);
      final data = await _image!.readAsBytes();
      ui.decodeImageFromList(data, (ui.Image img) {
        setState(() {
          image = img; // Initialize image
          doFaceDetection();
        });
      });
    }
  }

  //TODO choose image using gallery
  _imgFromGallery() async {
    XFile? pickedFile = await imagePicker.pickImage(
      source: ImageSource.gallery,
    );
    if (pickedFile != null) {
      _image = File(pickedFile.path);
      final data = await _image!.readAsBytes();
      ui.decodeImageFromList(data, (ui.Image img) {
        setState(() {
          image = img; // Initialize image
          doFaceDetection();
        });
      });
    }
  }

  //TODO face detection code here
  List<Face> faces = [];

  doFaceDetection() async {
    // Remove rotation of camera images
    await removeRotation(_image!);

    InputImage inputImage = InputImage.fromFile(_image!);

    // Passing input to face detector and getting detected faces
    faces = await faceDetector.processImage(inputImage);

    if (faces.isNotEmpty) {
      for (Face face in faces) {
        cropAndRegisterFace(face.boundingBox);
      }
    } else {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text("No faces detected")));
    }
  }

  cropAndRegisterFace(Rect boundingBox) {
    num left = boundingBox.left < 0 ? 0 : boundingBox.left;
    num top = boundingBox.top < 0 ? 0 : boundingBox.top;
    num right =
        boundingBox.right > image!.width ? image!.width - 1 : boundingBox.right;
    num bottom =
        boundingBox.bottom > image!.height
            ? image!.height - 1
            : boundingBox.bottom;
    num width = right - left;
    num height = bottom - top;

    final bytes = _image!.readAsBytesSync();
    img.Image? faceImg = img.decodeImage(bytes!);
    img.Image croppedFace = img.copyCrop(
      faceImg!,
      x: left.toInt(),
      y: top.toInt(),
      width: width.toInt(),
      height: height.toInt(),
    );

    Recognition recognition = recognizer.recognize(croppedFace, boundingBox);
    showRecognitionResultDialog(
      Uint8List.fromList(img.encodeBmp(croppedFace)),
      recognition,
    );
  }

  showRecognitionResultDialog(Uint8List croppedFace, Recognition recognition) {
    showDialog(
      context: context,
      builder:
          (ctx) => AlertDialog(
            title: const Text(
              "Recognition Result",
              textAlign: TextAlign.center,
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Image.memory(croppedFace, width: 200, height: 200),
                const SizedBox(height: 10),
                Text(
                  recognition.name.isNotEmpty
                      ? "Student: ${recognition.name}"
                      : "روح سجل الاول",
                  style: const TextStyle(fontSize: 18),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.pop(context);
                },
                child: const Text("OK"),
              ),
            ],
          ),
    );
  }

  // Remove rotation of camera images
  removeRotation(File inputImage) async {
    final img.Image? capturedImage = img.decodeImage(
      await File(inputImage.path).readAsBytes(),
    );
    final img.Image orientedImage = img.bakeOrientation(capturedImage!);
    await File(_image!.path).writeAsBytes(img.encodeJpg(orientedImage));
  }

  //TODO perform Face Recognition

  //TODO Face Registration Dialogue
  TextEditingController textEditingController = TextEditingController();

  showFaceRegistrationDialogue(Uint8List cropedFace, Recognition recognition) {
    showDialog(
      context: context,
      builder:
          (ctx) => AlertDialog(
            title: const Text("Face Registration", textAlign: TextAlign.center),
            alignment: Alignment.center,
            content: SizedBox(
              height: 340,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const SizedBox(height: 20),
                  Image.memory(cropedFace, width: 200, height: 200),
                  SizedBox(
                    width: 200,
                    child: TextField(
                      controller: textEditingController,
                      decoration: const InputDecoration(
                        fillColor: Colors.white,
                        filled: true,
                        hintText: "Enter Name",
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  ElevatedButton(
                    onPressed: () {
                      recognizer.registerFaceInDB(
                        textEditingController.text,
                        recognition.embeddings,
                      );
                      textEditingController.text = "";
                      Navigator.pop(context);
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text("Face Registered")),
                      );
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blue,
                      minimumSize: const Size(200, 40),
                    ),
                    child: const Text("Register"),
                  ),
                ],
              ),
            ),
            contentPadding: EdgeInsets.zero,
          ),
    );
  }

  //TODO draw rectangles
  drawRectangleAroundFaces() async {
    print("${image!.width}   ${image!.height}");
    setState(() {
      image;
      faces;
    });
  }

  @override
  Widget build(BuildContext context) {
    double screenWidth = MediaQuery.of(context).size.width;
    double screenHeight = MediaQuery.of(context).size.height;
    return Scaffold(
      resizeToAvoidBottomInset: false,
      body: Column(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          _image != null && image != null
              ? Container(
                margin: const EdgeInsets.only(
                  top: 60,
                  left: 30,
                  right: 30,
                  bottom: 0,
                ),
                child: FittedBox(
                  child: SizedBox(
                    width: image!.width.toDouble(),
                    height: image!.width.toDouble(),
                    child: CustomPaint(
                      painter: FacePainter(facesList: faces, imageFile: image),
                    ),
                  ),
                ),
              )
              : Container(
                margin: const EdgeInsets.only(top: 100),
                child: Image.asset(
                  "images/logo.png",
                  width: screenWidth - 100,
                  height: screenWidth - 100,
                ),
              ),

          Container(height: 50),

          //TODO section which displays buttons for choosing and capturing images
          Container(
            margin: const EdgeInsets.only(bottom: 50),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                Card(
                  shape: const RoundedRectangleBorder(
                    borderRadius: BorderRadius.all(Radius.circular(200)),
                  ),
                  child: InkWell(
                    onTap: () {
                      _imgFromGallery();
                    },
                    child: SizedBox(
                      width: screenWidth / 2 - 70,
                      height: screenWidth / 2 - 70,
                      child: Icon(
                        Icons.image,
                        color: Colors.blue,
                        size: screenWidth / 7,
                      ),
                    ),
                  ),
                ),
                Card(
                  shape: const RoundedRectangleBorder(
                    borderRadius: BorderRadius.all(Radius.circular(200)),
                  ),
                  child: InkWell(
                    onTap: () {
                      _imgFromCamera();
                    },
                    child: SizedBox(
                      width: screenWidth / 2 - 70,
                      height: screenWidth / 2 - 70,
                      child: Icon(
                        Icons.camera,
                        color: Colors.blue,
                        size: screenWidth / 7,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class FacePainter extends CustomPainter {
  List<Face> facesList;
  ui.Image? imageFile; // Use ui.Image type
  FacePainter({required this.facesList, @required this.imageFile});

  @override
  void paint(Canvas canvas, Size size) {
    if (imageFile != null) {
      canvas.drawImage(imageFile!, Offset.zero, Paint());
    }

    Paint p = Paint();
    p.color = Colors.red;
    p.style = PaintingStyle.stroke;
    p.strokeWidth = 3;

    for (Face face in facesList) {
      canvas.drawRect(face.boundingBox, p);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) {
    return true;
  }
}
