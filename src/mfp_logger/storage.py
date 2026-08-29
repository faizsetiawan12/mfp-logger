import os
from typing import Optional

class ImageStorage:
    def __init__(self, base_dir: str = "/tmp/mfp_images"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def cleanup_image(self, file_path: str, retain_for_recipe: bool = False) -> bool:
        if retain_for_recipe:
            return False
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except OSError:
                return False
        return False
