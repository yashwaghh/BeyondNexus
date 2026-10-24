"""Package only the local extension runtime and its setup instructions."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = ('manifest.json', 'service_worker.js', 'popup.html', 'popup.js',
         'popup.css', 'composer.js', 'attachment.js', 'preview.js', 'options.html', 'options.js', 'README.md')

if __name__ == '__main__':
    # Keep the unpacked extension's shared renderer in sync with the Python UI.
    (ROOT / 'extension' / 'preview.js').write_bytes((ROOT / 'privacygate' / 'ui' / 'preview.js').read_bytes())
    destination = ROOT / 'dist' / 'privacygate-extension.zip'
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / 'extension' / name, name)
    print(f'Packaged {len(FILES)} extension files: {destination}')
