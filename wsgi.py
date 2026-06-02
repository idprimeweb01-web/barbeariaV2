import os
import traceback

print(f"DATABASE_URL = {repr(os.getenv('DATABASE_URL'))}", flush=True)
print(f"FLASK_APP = {repr(os.getenv('FLASK_APP'))}", flush=True)

try:
    from app import create_app
    app = create_app()
    print("SUCCESS: app created OK", flush=True)
except Exception as e:
    print(f"FATAL ERROR during app creation: {e}", flush=True)
    traceback.print_exc()
    raise


@app.route('/test')
def test():
    return {'status': 'ok'}, 200

if __name__ == "__main__":
    app.run()
