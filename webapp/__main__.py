import argparse

import uvicorn

from webapp.gallery.config import DB_PATH, GROUP_ID, HOST, IMAGE_ROOT, ONEBOT_HTTP_URL, PORT


def main():
    parser = argparse.ArgumentParser(description="BotEro 打卡图片瀑布流浏览")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    print(f"数据库: {DB_PATH}")
    print(f"图片目录: {IMAGE_ROOT}")
    print(f"OneBot HTTP: {ONEBOT_HTTP_URL}（群 {GROUP_ID}，用于昵称）")
    print(f"访问: http://{args.host}:{args.port}/")

    uvicorn.run(
        "webapp.app:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
