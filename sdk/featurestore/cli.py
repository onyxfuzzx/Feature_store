import argparse
import json
import sys
from featurestore.client import FeatureStoreClient, FeatureStoreError


def main():
    parser = argparse.ArgumentParser(prog="featurestore", description="Feature Store & Model Registry CLI")
    parser.add_argument("--url", default="http://localhost:8000", help="Feature Store API base URL")
    parser.add_argument("--api-key", default=None, help="API Key for authentication")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: login
    login_parser = subparsers.add_parser("login", help="Log in and retrieve JWT token")
    login_parser.add_argument("--email", required=True, help="User email")
    login_parser.add_argument("--password", required=True, help="User password")

    # Command: features
    subparsers.add_parser("features", help="List registered feature definitions")

    # Command: models
    subparsers.add_parser("models", help="List registered models in registry")

    # Command: get-online
    online_parser = subparsers.add_parser("get-online", help="Fetch real-time features for entity keys")
    online_parser.add_argument("--keys", required=True, nargs="+", help="Entity keys")
    online_parser.add_argument("--features", required=True, nargs="+", help="Feature names")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = FeatureStoreClient(api_url=args.url, api_key=args.api_key)

    try:
        if args.command == "login":
            res = client.login(args.email, args.password)
            print(f"Logged in successfully as {res['user']['name']}.")
            print(f"Token: {res['access_token']}")
        elif args.command == "features":
            feats = client.list_features()
            print(f"Found {len(feats)} features:")
            for f in feats:
                print(f"  - {f['name']} ({f['dtype']}) | status: {f['status']}")
        elif args.command == "models":
            models = client.list_models()
            print(f"Found {len(models)} models:")
            for m in models:
                print(f"  - {m['name']} | env: {m['environment']}")
        elif args.command == "get-online":
            res = client.get_online_features(entity_keys=args.keys, features=args.features)
            print(json.dumps(res, indent=2))
    except FeatureStoreError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
