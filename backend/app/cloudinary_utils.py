import cloudinary
import cloudinary.uploader
import os


cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)


def upload_image_bytes(data: bytes, filename: str) -> dict:
    result = cloudinary.uploader.upload(
        data,
        resource_type="image",
        folder="og-ecosystem/posts",
        public_id=filename.rsplit(".", 1)[0],
        overwrite=False,
    )

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
    }