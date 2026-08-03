from django.shortcuts import render
from django.core.paginator import Paginator
from config.db import db

# Sumber data utama foto event lari (hasil sinkronisasi lomba_lari + metadata)
PHOTO_COLLECTION = 'photos_photoevent'
ITEMS_PER_PAGE = 24

koleksi_foto_event = db[PHOTO_COLLECTION]


def _folder_event(image_path):
    """Ambil nama folder event dari path image 'lomba_lari/<folder>/<file>'.

    Contoh:
      'lomba_lari/colorun/ColorRun_Fest(1).jpg' -> 'colorun'
      'lomba_lari/tientorun/Tiento_Run(1).JPG'  -> 'tientorun'
    """
    if not image_path:
        return ''
    img = image_path.replace('\\', '/')
    parts = [p for p in img.split('/') if p]
    if len(parts) >= 3 and parts[0].lower() == 'lomba_lari':
        return parts[1]
    return ''


def _image_url(image_path):
    """URL /media/... untuk foto event.

    Selalu `lomba_lari/<folder>/<file>` karena file asli ada di
    media/lomba_lari/<folder>/ (data sumber di folder recog via junction).
    """
    if not image_path:
        return ''
    img = image_path.replace('\\', '/')
    return f"/media/{img}"


def _folder_label(folder):
    """Label event yang ramah dari nama folder.

    Mis. 'colorun' -> 'Color Run', 'milo_race_2026' -> 'Milo Race 2026'.
    """
    mapping = {
        'tientorun': 'Tiento Run',
        'colorun': 'Color Run',
        'carfreeday': 'Car Free Day',
        'milo': 'Milo',
        'milo_race_2026': 'Milo Race 2026',
        'merdeka': 'Kemerdekaan',
        'kemerdekaan': 'Kemerdekaan',
        'ui_ecorun': 'UI ECO Run',
    }
    if folder in mapping:
        return mapping[folder]
    return folder.replace('_', ' ').title()


def _list_folders():
    """Kumpulan folder event unik (dari path image di DB)."""
    folders = set()
    for d in koleksi_foto_event.find({}, {'image': 1}):
        f = _folder_event(d.get('image'))
        if f:
            folders.add(f)
    return sorted(folders)


def foto_user(request):
    """Halaman gallery browsing foto event lari."""
    folder_list = _list_folders()
    return render(request, 'galeri/foto/foto.html', {
        'active_page': 'search',
        'folder_list': folder_list,
    })


def hasil(request):
    """Hasil gallery browsing: filter by folder event + pagination."""
    folder = (request.GET.get('folder') or '').strip()

    query = {}
    if folder:
        # filter via regex pada path image 'lomba_lari/<folder>/...'
        query = {'image': {'$regex': f'^lomba_lari/{folder}/'}}

    cursor = koleksi_foto_event.find(query).sort('id', 1)
    fotos = []
    for d in cursor:
        image_path = d.get('image', '')
        f = _folder_event(image_path)
        fotos.append({
            'id': d.get('id'),
            'image': _image_url(image_path),
            'folder': f,
            'folder_label': _folder_label(f),
            'event_name': d.get('event_name', ''),
            'bib_number': d.get('bib_number', ''),
            'uploaded_at': d.get('uploaded_at'),
        })

    paginator = Paginator(fotos, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(int(request.GET.get('page', 1)))

    return render(request, 'galeri/foto/hasil.html', {
        'active_page': 'search',
        'page_obj': page_obj,
        'fotos': page_obj.object_list,
        'folder_selected': folder,
        'folder_label': _folder_label(folder) if folder else '',
        'total': paginator.count,
    })
