from io import BytesIO
from functools import lru_cache

try:
    import dlib
    import numpy as np
    import face_recognition_models
    from PIL import Image, UnidentifiedImageError
except (ImportError, OSError):
    dlib = None
    np = None
    face_recognition_models = None
    Image = None
    UnidentifiedImageError = OSError


class FaceRecognitionUnavailable(Exception):
    pass


class InvalidFaceImage(Exception):
    pass


@lru_cache(maxsize=1)
def _face_models():
    if dlib is None or face_recognition_models is None:
        raise FaceRecognitionUnavailable
    return (
        dlib.get_frontal_face_detector(),
        dlib.shape_predictor(face_recognition_models.pose_predictor_model_location()),
        dlib.face_recognition_model_v1(face_recognition_models.face_recognition_model_location()),
    )


def extract_face_encoding(image_bytes):
    if dlib is None or np is None or Image is None or face_recognition_models is None:
        raise FaceRecognitionUnavailable

    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image_array = np.array(image)
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise InvalidFaceImage("O arquivo enviado não é uma imagem válida.") from error

    detector, predictor, face_encoder = _face_models()
    locations = detector(image_array, 1)
    if not locations:
        raise InvalidFaceImage("Nenhum rosto foi detectado. Tente novamente com boa iluminação.")
    if len(locations) != 1:
        raise InvalidFaceImage("A imagem precisa mostrar somente um rosto.")

    landmarks = predictor(image_array, locations[0])
    return list(face_encoder.compute_face_descriptor(image_array, landmarks))


def face_matches(registered_encoding, submitted_encoding, tolerance=0.6):
    if np is None:
        raise FaceRecognitionUnavailable
    if len(registered_encoding) != 128 or len(submitted_encoding) != 128:
        return False

    distance = np.linalg.norm(
        np.asarray(registered_encoding, dtype=float) - np.asarray(submitted_encoding, dtype=float)
    )
    return bool(np.isfinite(distance) and distance <= tolerance)
