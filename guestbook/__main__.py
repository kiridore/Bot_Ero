import argparse

import uvicorn

from core.config import HOST


def main():
    parser = argparse.ArgumentParser(description="BotEro 留言簿")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    print(f"访问: http://{args.host}:{args.port}/")
    uvicorn.run("guestbook.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
