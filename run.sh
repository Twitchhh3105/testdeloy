#!/bin/bash
# Kích hoạt môi trường ảo
source .venv/bin/activate

# Chạy server với chế độ tự động reload khi code thay đổi
uvicorn api.server:app --reload
