from pathlib import Path

from django.conf import settings
from rest_framework import serializers

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_IMAGE_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


def _is_valid_image_binary(uploaded_file):
    uploaded_file.seek(0)
    header = uploaded_file.read(32)

    is_jpeg = header.startswith(b'\xff\xd8\xff')
    is_png = header.startswith(b'\x89PNG\r\n\x1a\n')
    is_webp = header.startswith(b'RIFF') and len(header) >= 12 and header[8:12] == b'WEBP'
    return is_jpeg or is_png or is_webp


def validate_image_upload(uploaded_file):
    if not uploaded_file:
        return uploaded_file

    extension = Path(uploaded_file.name or '').suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise serializers.ValidationError('Extensión de archivo no permitida. Use: .jpg, .jpeg, .png o .webp.')

    content_type = getattr(uploaded_file, 'content_type', None)
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise serializers.ValidationError('Tipo de archivo no permitido. Solo se aceptan image/jpeg, image/png o image/webp.')

    max_size = settings.MAX_UPLOAD_IMAGE_SIZE_BYTES
    if uploaded_file.size > max_size:
        max_size_mb = settings.MAX_UPLOAD_IMAGE_SIZE_MB
        raise serializers.ValidationError(f'La imagen supera el tamaño máximo permitido de {max_size_mb} MB.')

    try:
        if not _is_valid_image_binary(uploaded_file):
            raise serializers.ValidationError('El archivo no es una imagen válida.')
    finally:
        uploaded_file.seek(0)

    return uploaded_file
