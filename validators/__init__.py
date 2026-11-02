"""校验层：条数、去重、格式与完整性校验。"""

from .checks import validate_kugou_kgl, validate_payload, validate_playlist

__all__ = ["validate_kugou_kgl", "validate_payload", "validate_playlist"]
