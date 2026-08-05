import argparse
import os

import uvicorn

from gallery.config import DB_PATH, GROUP_ID, HOST, IMAGE_ROOT, ONEBOT_HTTP_URL, PORT


def main():
    parser = argparse.ArgumentParser(description="BotEro 打卡图片瀑布流浏览")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--db", default=None, help="data.db 路径")
    parser.add_argument("--images", default=None, help="record_images 根目录")
    args = parser.parse_args()

    if args.db:
        os.environ["BOTERO_DB_PATH"] = os.path.abspath(args.db)
    if args.images:
        os.environ["BOTERO_IMAGE_ROOT"] = os.path.abspath(args.images)

    db = os.environ.get("BOTERO_DB_PATH", str(DB_PATH))
    images = os.environ.get("BOTERO_IMAGE_ROOT", str(IMAGE_ROOT))
    print(f"数据库: {db}")
    print(f"图片目录: {images}")
    print(f"OneBot HTTP: {ONEBOT_HTTP_URL}（群 {GROUP_ID}，用于昵称）")
    print(f"访问: http://{args.host}:{args.port}/")

    uvicorn.run(
        "gallery.app:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
