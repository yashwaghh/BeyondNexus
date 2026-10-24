"""Synthetic-only browser test server. Never use this fake model for real review."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from privacygate.model import VisionFinding
from privacygate.web import create_server

class SyntheticVision:
    def detect_image(self, _data, _media_type):
        return [VisionFinding('AADHAAR', .55, 'gemma_vision', 'Synthetic test box', (500, 100, 650, 850)),
                VisionFinding('PERSON', .55, 'gemma_vision', 'Synthetic unlocated finding', None)]

if __name__ == '__main__':
    server = create_server(port=int(sys.argv[2]) if len(sys.argv) > 2 else 0,
                           token='synthetic-browser-token-1234567890',
                           extension_origin=sys.argv[1] if len(sys.argv) > 1 else None,
                           model=SyntheticVision())
    print(json.dumps({'origin': server.local_origin}), flush=True)
    server.serve_forever()
