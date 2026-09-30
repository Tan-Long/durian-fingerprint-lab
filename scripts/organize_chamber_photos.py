#!/usr/bin/env python3
"""Review label crops, then copy originals into fruit folders without changing sources."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from urllib.request import urlopen

from scripts.build_hoc_manifest import discover_images


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def prepare(source, output):
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(source.resolve()):
        raise ValueError('Use a new review output outside the original source directory')
    cameras = {'Máy IP12': 'ip12', 'Máy IP17': 'ip17', 'Máy Đăng': 'dang'}
    folders = {cameras[unicodedata.normalize('NFC', p.name)]: p for p in source.iterdir()
               if p.is_dir() and unicodedata.normalize('NFC', p.name) in cameras}
    if len(folders) != 3:
        raise ValueError('Expected the three original camera directories')
    output.mkdir(parents=True)
    records = []
    for camera, folder in sorted(folders.items()):
        for index, path in enumerate(discover_images(folder)):
            records.append({'camera': camera, 'index': index, 'relative_path': str(path.relative_to(source)),
                            'source_path': str(path), 'sha256': digest(path), 'size': path.stat().st_size})
    (output / 'inventory.json').write_text(json.dumps({'source': str(source), 'files': records}, ensure_ascii=False, indent=2)+'\n')
    make_previews(records, output)


def make_previews(records, output):
    def preview(record):
        # Existing local review server already has bounded, hash-checked JPEG previews.
        media_id = 'media-' + hashlib.sha256(record['source_path'].encode()).hexdigest()
        with urlopen('http://127.0.0.1:8765/media/' + media_id, timeout=60) as response:
            content = response.read()
        target = output / record['camera']
        target.mkdir(exist_ok=True)
        name = f"{record['index']:03d}"
        (target / (name + '.jpg')).write_bytes(content)
        subprocess.run(['magick', 'jpeg:-', '-gravity', 'south', '-crop', '100%x42%+0+0', '+repage',
                        '-resize', '900x420>', '-background', 'white', '-gravity', 'center', '-extent', '900x420',
                        '-gravity', 'north', '-splice', '0x36', '-font', '/System/Library/Fonts/Supplemental/Arial.ttf', '-pointsize', '22',
                        '-fill', 'black', '-annotate', '+0+6', f"{name}: {Path(record['source_path']).name}",
                        str(target / (name + '-label.jpg'))], input=content, check=True, capture_output=True)
        return record

    with ThreadPoolExecutor(max_workers=2) as workers:
        for index, _ in enumerate(workers.map(preview, records), 1):
            if index % 30 == 0:
                print(f'Previews {index}/{len(records)}', flush=True)
    make_sheets(records, output)


def make_sheets(records, output):
    for camera in sorted({record['camera'] for record in records}):
        labels = sorted((output / camera).glob('*-label.jpg'))
        for offset in range(0, len(labels), 12):
            subprocess.run(['magick', 'montage', '-font', '/System/Library/Fonts/Supplemental/Arial.ttf', *map(str, labels[offset:offset+12]), '-tile', '2x',
                            '-geometry', '+0+0', str(output / camera / f'sheet-{offset:03d}.jpg')], check=True)
    print(f'Prepared {len(records)} source photos at {output}', flush=True)


def copy_reviewed(inventory, reviews, destination):
    source = Path(inventory['source']).resolve(strict=True)
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink() or destination.resolve().is_relative_to(source):
        raise ValueError('Use a new destination outside the original source directory')
    records = inventory['files']
    if len(records) != len(reviews) or set(reviews) != {r['relative_path'] for r in records}:
        raise ValueError('Review must account for every original exactly once')
    plan = []
    for record in records:
        relative_source = Path(record['relative_path'])
        if relative_source.is_absolute() or '..' in relative_source.parts:
            raise ValueError('Source name must be relative without traversal')
        path = source / relative_source
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):
            raise ValueError('Source path escapes the original directory')
        review = reviews[record['relative_path']]
        code = review['fruit_id']
        status = review['status']
        if status not in {'visual_read', 'unclear', 'not_labelled'}:
            raise ValueError('Unknown visual review status')
        if code and (status != 'visual_read' or not re.fullmatch(r'N[1-9]\d*V[1-9]\d*C[1-9]\d*(?:_BONUS)?', code)):
            raise ValueError('Fruit folders require a clear visual reading of a complete fruit code')
        if status == 'visual_read' and not code:
            raise ValueError('Visual reading requires a fruit code')
        if not isinstance(review.get('note'), str) or not review['note'].strip():
            raise ValueError('Every photo needs a visual evidence/ambiguity note')
        if digest(path) != record['sha256']:
            raise ValueError(f'Source content changed: {path}')
        group = code or ('_KHONG_CO_NHAN_QUA' if status == 'not_labelled' else '_CHUA_RO_NHAN')
        relative = Path(group) / record['relative_path']
        plan.append((record, review, path, relative))
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, (record, review, path, relative) in enumerate(plan, 1):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with path.open('rb') as original, target.open('xb') as copied:
            shutil.copyfileobj(original, copied)
        if digest(target) != record['sha256'] or digest(path) != record['sha256']:
            raise ValueError(f'Copy verification failed; retain partial output for inspection: {target}')
        shutil.copystat(path, target)
        rows.append({**record, **review, 'destination': str(target), 'user_approved': False})
        if index % 50 == 0:
            print(f'Copied and verified {index}/{len(plan)}', flush=True)
    (destination / 'DOI_CHIEU_ANH.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
    with (destination / 'DOI_CHIEU_ANH.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (destination / 'README.txt').write_text(
        'Bản sao sắp xếp theo nhãn quả đọc trực tiếp trên ảnh; chưa phải nhãn đã được người dùng duyệt.\n'
        'Giữ nguyên tên ảnh và thư mục máy chụp bên trong mỗi mã quả. Không sửa/move ảnh gốc.\n'
        'Ảnh mờ/mâu thuẫn nằm ở _CHUA_RO_NHAN; ảnh không thấy mã quả nằm ở _KHONG_CO_NHAN_QUA.\n'
        'Không suy ra số hộc hay số múi từ số ảnh. DOI_CHIEU_ANH lưu nguồn, hash và ghi chú cho từng file.\n', encoding='utf-8')
    print(f'Copied and hash-verified {len(rows)} photos to {destination}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--source', type=Path, required=True)
    prep.add_argument('--output', type=Path, required=True)
    apply = commands.add_parser('copy')
    apply.add_argument('--inventory', type=Path, required=True)
    apply.add_argument('--reviews', type=Path, nargs='+', required=True)
    apply.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.source.resolve(strict=True), args.output.resolve())
    else:
        reviews = {}
        for path in args.reviews:
            records = json.loads(path.read_text())
            if set(records) & set(reviews):
                raise ValueError('Duplicate review assignment')
            reviews.update(records)
        copy_reviewed(json.loads(args.inventory.read_text()), reviews, args.destination)


if __name__ == '__main__':
    main()
