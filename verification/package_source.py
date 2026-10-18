"""Create the local-service source zip without dependencies or runtime state."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
ROOT = Path(__file__).resolve().parents[1]
source = ROOT/'fullstack/device-desk'
files = [source/name for name in ['package.json', 'package-lock.json', 'app.js', 'server.js', 'README.md']]
files += sorted((source/'public').glob('*')) + sorted((source/'test').glob('*.js'))
with ZipFile(ROOT/'downloads/device-desk-source.zip', 'w', ZIP_DEFLATED) as archive:
    for path in files: archive.write(path, Path('device-desk')/path.relative_to(source))
    for name in ['REPORT.md','api-tests.txt']:
        archive.write(ROOT/'verification'/name,Path('device-desk/docs')/name)
    review = ROOT/'verification/PREPUBLISH_REVIEW.md'
    if review.is_file():
        archive.write(review,Path('device-desk/docs/PREPUBLISH_REVIEW.md'))
print(f'device-desk-source.zip: {len(files)} source files')
