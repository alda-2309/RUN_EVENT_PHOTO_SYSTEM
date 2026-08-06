from django.shortcuts import render
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from config.db import db

# Sumber data utama foto event lari (hasil sinkronisasi lomba_lari + metadata)
PHOTO_COLLECTION = 'photos_photoevent'
ITEMS_PER_PAGE = 25

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


def _list_jenis_event():
    """Kumpulan jenis event unik dari data galeri."""
    return sorted(x for x in koleksi_foto_event.distinct('jenis_event') if x)


def _build_query(request):
    """Bangun query Mongo dari filter GET (folder, jenis event, timestamp)."""
    folder = (request.GET.get('folder') or '').strip()
    jenis = (request.GET.get('jenis') or '').strip()
    tanggal = (request.GET.get('tanggal') or '').strip()

    query = {}
    if folder:
        # filter via regex pada path image 'lomba_lari/<folder>/...'
        query['image'] = {'$regex': '^lomba_lari/%s/' % folder}
    if jenis:
        query['jenis_event'] = jenis
    if tanggal:
        try:
            d = datetime.strptime(tanggal, '%Y-%m-%d')
            query['timestamp'] = {'$gte': d, '$lt': d + timedelta(days=1)}
        except ValueError:
            pass
    return query, folder, jenis, tanggal


def _get_fotos(query):
    """Ambil daftar foto dari collection sesuai query, urut by id."""
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
            'jenis_event': d.get('jenis_event', ''),
            'timestamp': d.get('timestamp'),
            'bib_number': d.get('bib_number', ''),
            'uploaded_at': d.get('uploaded_at'),
        })
    return fotos


def _build_context(request, template):
    """Context galeri: semua foto (tanpa wajib pilih folder) + filter."""
    query, folder, jenis, tanggal = _build_query(request)
    fotos = _get_fotos(query)

    paginator = Paginator(fotos, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(int(request.GET.get('page', 1)))

    return render(request, template, {
        'active_page': 'search',
        'page_obj': page_obj,
        'fotos': page_obj.object_list,
        'folder_list': _list_folders(),
        'jenis_list': _list_jenis_event(),
        'folder_selected': folder,
        'jenis_selected': jenis,
        'tanggal': tanggal,
        'total': paginator.count,
    })


def foto_user(request):
    """Halaman gallery foto event — langsung tampilkan semua foto."""
    return _build_context(request, 'galeri/foto/foto.html')


def hasil(request):
    """Hasil gallery browsing: filter folder/jenis event/timestamp + pagination."""
    return _build_context(request, 'galeri/foto/hasil.html')
