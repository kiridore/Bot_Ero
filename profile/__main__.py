import argparse

import uvicorn

from core.config import HOST


def main():
    parser = argparse.ArgumentParser(description="BotEro 个人中心")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    print(f"访问: http://{args.host}:{args.port}/")
    uvicorn.run("profile.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
