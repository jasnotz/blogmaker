import os, sys, datetime, json, re, posixpath, subprocess, shlex, shutil, itertools
from collections import defaultdict
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

PRE_HEADER = """

<!DOCTYPE html>
<html>
<meta charset="UTF-8">
<style>
@media (prefers-color-scheme: dark) {
    body {
        background-color: #1c1c1c;
        color: white;
    }
    .markdown-body table tr {
        background-color: #1c1c1c;
    }
    .markdown-body table tr:nth-child(2n) {
        background-color: black;
    }
}
</style>

"""

HEADER_TEMPLATE = r"""

<link rel="stylesheet" type="text/css" href="$root/css/main.css">

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Mono:wght@400;500;600;700&family=Noto+Serif+KR:wght@300;400;500;600;700;900&display=swap" rel="stylesheet">

<link rel="stylesheet" type="text/css" href="$root/css/pandoc-highlight.css">

<script>
  window.MathJax = {
    tex: {
      inlineMath: [['\\(', '\\)'], ['$', '$']],
      displayMath: [['\\[', '\\]'], ['$$', '$$']],
      processEscapes: true,
      packages: {'[+]': ['ams', 'noerrors']}
    },
    svg: {
      fontCache: 'global'
    }
  };
</script>

<script type="text/javascript" id="MathJax-script" async
  src="$root/scripts/tex-svg.js">
</script>


<style>

body, .markdown-body {
  font-family:
    "Noto Sans Mono",
    "Noto Serif KR",
    monospace;
}

</style>


<div id="doc" class="container-fluid markdown-body comment-enabled" data-hard-breaks="true">


<div id="color-mode-switch">

  <svg xmlns="http://www.w3.org/2000/svg"
       class="h-6 w-6"
       fill="none"
       viewBox="0 0 24 24"
       stroke="currentColor"
       stroke-width="2">

    <path stroke-linecap="round"
          stroke-linejoin="round"
          d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />

  </svg>


  <input type="checkbox" id="switch" />

  <label for="switch">
    Dark Mode Toggle
  </label>


  <svg xmlns="http://www.w3.org/2000/svg"
       class="h-6 w-6"
       fill="none"
       viewBox="0 0 24 24"
       stroke="currentColor"
       stroke-width="2">

    <path stroke-linecap="round"
          stroke-linejoin="round"
          d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />

  </svg>


</div>

"""

TOGGLE_COLOR_SCHEME_JS = """
<script type="text/javascript">
  const toggleDarkMode = () => {
    document.querySelector('html').classList.toggle('dark');
  }
  const toggleColorScheme = () => {
    const colorScheme = localStorage.getItem('colorScheme');
    if (colorScheme === 'light') localStorage.setItem('colorScheme', 'dark');
    else localStorage.setItem('colorScheme', 'light');
  }
  const toggle = document.querySelector('#color-mode-switch input[type="checkbox"]');
  if (toggle) toggle.onclick = () => {
    toggleDarkMode();
    toggleColorScheme();
  }
  const checkColorScheme = () => {
    const colorScheme = localStorage.getItem('colorScheme');
    if (colorScheme === null || colorScheme === undefined) localStorage.setItem('colorScheme', 'light');
    if (colorScheme === 'dark') {
      toggle.checked = true;
      toggleDarkMode();
    }
  }
  checkColorScheme();
</script>
"""

RSS_LINK = """

<link rel="alternate" type="application/rss+xml" href="{}/feed.xml" title="{}">

"""

TITLE_TEMPLATE = """

<br>
<h1 style="margin-bottom:7px"> {0} </h1>

<small style="float:left; color:#888"> {1} </small>
<small style="float:right; color:#888">
<a href="{2}/index.html">See all posts</a>
</small>

<br><br><br>

<title>{0}</title>

"""

TOC_TITLE_TEMPLATE = """

<title> {0} </title>

<br>

<center>
<h1 style="border-bottom:0px">
{0}
</h1>

<p style="
    margin-top:0;
    margin-bottom:10px;
    color:#888;
    font-size:0.95rem;
">
김현석의 블로그입니다
</p>

</center>

"""

HOME_BUTTON_TEMPLATE = """

<center>
  <a href="{0}/index.html" style="text-decoration:none; color:#888; font-size:90%;">&larr; 홈으로 돌아가기</a>
</center>
<br>

"""

FOOTER = """ </div> """

TOC_START = """

<br>
<ul class="post-list" style="padding-left:0">

"""

TOC_END = """ </ul> """

TOC_ITEM_TEMPLATE = """

<li>
    <span class="post-meta">{0}</span>
    <span class="post-category" style="color:#888; margin-left:8px;">{3}</span>
    <h3 style="margin-top:12px">
      <a class="post-link" href="{1}">{2}</a>
    </h3>
</li>

"""

TWITTER_CARD_TEMPLATE = """
<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="{}" />
<meta name="twitter:image" content="{}" />
"""


RSS_ITEM_TEMPLATE = """
<item>
<title>{title}</title>
<link>{link}</link>
<guid>{link}</guid>
<pubDate>{pub_date}</pubDate>
<description>{description}</description>
</item>
"""


RSS_MAIN_TEMPLATE = """
<?xml version="1.0" ?>
<rss version="2.0">
<channel>
  <title>{title}</title>
  <link>{link}</link>
  <description>{title}</description>
  <image>
      <url>{icon}</url>
      <title>{title}</title>
      <link>{link}</link>
  </image>
{items}
</channel>
</rss>
"""

SEARCH_UI_TEMPLATE = """
<link rel="stylesheet" type="text/css" href="$root/css/search-ui.css">
<div id="search-container">
  <input 
    type="search"
    id="search-input"
    autocomplete="off"
    placeholder="🔍 Search posts..."
    />
  <ul id="search-results"></ul>
  <div id="search-no-results">No posts found.</div>
</div>
"""

SEARCH_JS_TEMPLATE = """
<script src="$root/scripts/lunr.min.js"></script>
<script>
const SEARCH_DATA_EMBEDDED = __SEARCH_DATA_JSON__;

let searchIndex = null;
let searchDocuments = {};

function initializeSearch() {
  if (!window.lunr) {
    console.error('lunr.js not loaded');
    return;
  }
  searchDocuments = SEARCH_DATA_EMBEDDED.documents;
  try {
    searchIndex = lunr.Index.load(SEARCH_DATA_EMBEDDED.index);
  } catch (e) {
    console.error('검색 인덱스 로드 실패:', e);
  }
}

if (window.lunr) {
  initializeSearch();
} else {
  document.addEventListener('DOMContentLoaded', initializeSearch);
}

const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
const searchNoResults = document.getElementById('search-no-results');
const RESULTS_LIMIT = 10;
const PREVIEW_LENGTH = 150;

function runSearch(query) {
  if (!query || !searchIndex) {
    searchResults.style.display = 'none';
    searchNoResults.style.display = 'none';
    return;
  }
  try {
    const results = searchIndex.search(query);
    if (results.length === 0) {
      searchResults.style.display = 'none';
      searchNoResults.style.display = 'block';
      return;
    }
    const fragment = document.createDocumentFragment();
    for (const result of results.slice(0, RESULTS_LIMIT)) {
      const doc = searchDocuments[result.ref];
      if (!doc) continue;
      const li = document.createElement('li');
      let preview = doc.content.substring(0, PREVIEW_LENGTH);
      if (doc.content.length > PREVIEW_LENGTH) preview += '...';
      li.innerHTML = `
        <h4><a href="${doc.url}">${doc.title}</a></h4>
        <span class="search-date">${doc.date}</span>
        <span class="search-preview">${preview}</span>
      `;
      fragment.appendChild(li);
    }
    searchResults.innerHTML = '';
    searchResults.appendChild(fragment);
    searchNoResults.style.display = 'none';
    searchResults.style.display = 'block';
  } catch (err) {
    console.error('검색 오류:', err);
  }
}

if (searchInput) {
  let debounceHandle = null;
  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.trim();
    if (debounceHandle) clearTimeout(debounceHandle);
    debounceHandle = setTimeout(() => runSearch(query), 120);
  });

  window.addEventListener('load', () => {
    searchInput.focus();
  });
}
</script>
"""

_TAG_RE = re.compile(r'<[^>]+>')
_SCRIPT_STYLE_RE = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)
_ENTITY_RE = re.compile(r'&nbsp;|&lt;|&gt;|&amp;')
_ENTITY_MAP = {'&nbsp;': ' ', '&lt;': '<', '&gt;': '>', '&amp;': '&'}
_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
MATH_BLOCK_RE = re.compile(r'\$\$.*?\$\$', re.DOTALL)
BARE_UNDERLINE_RE = re.compile(r'^[=\-]+$')

def fix_math_setext_conflicts(text):
    """
    $$...$$ 블록 안에 '=' 또는 '-' 로만 이루어진 줄이 있으면
    pandoc이 이를 Setext 헤더 밑줄로 오인해서 수식이 깨진다.
    해당 줄을 바로 윗줄에 붙여서 이 충돌을 피한다.
    """
    def fix_block(match):
        block = match.group(0)
        lines = block.split('\n')
        fixed = []
        for line in lines:
            if BARE_UNDERLINE_RE.match(line.strip()) and fixed:
                fixed[-1] = fixed[-1].rstrip() + ' ' + line.strip()
            else:
                fixed.append(line)
        return '\n'.join(fixed)
    return MATH_BLOCK_RE.sub(fix_block, text)

IMAGE_LINK_RE = re.compile(r'(!\[[^\]]*\]\()([^)\s]+)((?:\s+"[^"]*")?\))')

def fix_image_paths(text, root_path):
    """
    마크다운 이미지 링크 안의 'images/...' 경로를,
    실제 출력 파일 위치(site/posts/년/월/일/파일.html) 기준
    상대경로(root_path/images/...)로 자동 변환한다.
    예: ../images/그림.jpg  ->  ../../../../images/그림.jpg
    """
    def fix_link(match):
        prefix, url, suffix = match.group(1), match.group(2), match.group(3)
        idx = url.rfind('images/')
        if idx == -1:
            return match.group(0)
        rest = url[idx + len('images/'):]
        new_url = posixpath.join(root_path, 'images', rest)
        return prefix + new_url + suffix
    return IMAGE_LINK_RE.sub(fix_link, text)

def extract_metadata(fil, filename=None):
    metadata = {}
    if filename:
        assert filename[-3:] == '.md'
        metadata["filename"] = filename[:-3] + '.html'
    while 1:
        pos = fil.tell()
        line = fil.readline()
        if line and line[0] == '[' and ']' in line:
            key = line[1:line.find(']')]
            value_start = line.find('(') + 1
            value_end = line.rfind(')')
            if key in ('category', 'categories'):
                metadata['categories'] = set([
                    x.strip().lower() for x in line[value_start:value_end].split(',')
                ])
                assert '' not in metadata['categories']
            else:
                metadata[key] = line[value_start:value_end]
        else:
            fil.seek(pos)
            break
    return metadata


def metadata_to_path(global_config, metadata):
    return os.path.join(
        global_config.get('posts_directory', 'posts'),
        metadata['date'],
        metadata['filename']
    )


def strip_html_tags(text):
    return _TAG_RE.sub('', text)


def extract_text_content(html_content, max_length=500):
    text = _SCRIPT_STYLE_RE.sub('', html_content)
    text = strip_html_tags(text)
    text = _ENTITY_RE.sub(lambda m: _ENTITY_MAP[m.group(0)], text)
    text = ' '.join(text.split())
    return text[:max_length]


def _read_doc_content(args):
    i, metadata, global_config = args
    path = metadata_to_path(global_config, metadata)
    url = path.replace(os.sep, '/')
    full_path = os.path.join('site', path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = extract_text_content(f.read())
    except Exception:
        content = ''
    return i, url, content


def generate_search_index(global_config, metadatas):
    documents = {}
    docs_for_index = [None] * len(metadatas)

    with ThreadPoolExecutor() as ex:
        for i, url, content in ex.map(
            _read_doc_content,
            ((i, m, global_config) for i, m in enumerate(metadatas))
        ):
            metadata = metadatas[i]
            doc_id = str(i)
            documents[doc_id] = {
                'title': metadata['title'],
                'date': get_printed_date(metadata),
                'url': url,
                'content': content
            }
            docs_for_index[i] = {
                'id': doc_id,
                'title': metadata['title'],
                'content': content,
                'date': metadata['date']
            }

    index_data = {
        'version': '2.3.9',
        'fields': [
            {'fieldName': 'title', 'boost': 10},
            {'fieldName': 'content', 'boost': 1}
        ],
        'docs': docs_for_index,
        'pipeline': ['stemmer']
    }

    return {
        'documents': documents,
        'index': index_data
    }


def generate_feed(global_config, metadatas):
    def get_link(route):
        return global_config['domain'] + "/" + route

    def get_date(date_text):
        year, month, day = (int(x) for x in date_text.split('/'))
        date = datetime.date(year, month, day)
        return date.strftime('%a, %d %b %Y 00:00:00 +0000')

    def get_item(metadata):
        return RSS_ITEM_TEMPLATE.format(
            title=metadata['title'],
            link=get_link('/'.join([global_config.get('posts_directory', 'posts'), metadata['date'], metadata['filename']])),
            pub_date=get_date(metadata['date']), description=''
        )

    return RSS_MAIN_TEMPLATE.strip().format(
        title=global_config['title'],
        link=get_link(''),
        icon=global_config['icon'],
        items="\n".join(map(get_item, metadatas))
    )


def make_twitter_card(title, global_config):
    return TWITTER_CARD_TEMPLATE.format(title, global_config['icon'])


def defancify(text):
    return text \
        .replace("'", "'") \
        .replace('"', '"') \
        .replace('"', '"') \
        .replace('…', '...') \


def make_categories_header(categories, root_path):
    template = '<span class="toc-category" style="font-size:{}%"><a href="{}/categories/{}.html">{}</a></span>'
    parts = [
        template.format(min(100, 900 // len(category)), root_path, category, category.capitalize())
        for category in categories
    ]
    return '<center><hr>\n' + '\n'.join(parts) + '\n<hr></center>'


@lru_cache(maxsize=None)
def _printed_date_from_str(date_str):
    year, month, day = date_str.split('/')
    return year + ' ' + _MONTHS[int(month) - 1] + ' ' + day


def get_printed_date(metadata):
    return _printed_date_from_str(metadata['date'])


def get_order(metadata):
    try:
        return int(metadata.get('order', 0))
    except ValueError:
        return 0


def format_categories(metadata):
    return ', '.join(c.capitalize() for c in sorted(metadata.get('categories', ())))


def make_toc_item(global_config, metadata, root_path):
    link = metadata_to_path(global_config, metadata)
    return TOC_ITEM_TEMPLATE.format(
        get_printed_date(metadata),
        root_path + '/' + link,
        metadata['title'],
        format_categories(metadata)
    )


def make_toc(toc_items, global_config, all_categories, category=None, include_search=False, search_index_data=None):
    if category:
        title = category.capitalize()
        root_path = '..'
    else:
        title = global_config['title']
        root_path = '.'

    search_section = ''
    if include_search and search_index_data:
        adjusted_documents = {}
        for doc_id, doc in search_index_data['documents'].items():
            adjusted_documents[doc_id] = dict(doc)
            adjusted_documents[doc_id]['url'] = posixpath.normpath(
                posixpath.join(root_path, doc['url'])
            )
        page_search_data = {
            'documents': adjusted_documents,
            'index': search_index_data['index'],
        }

        search_data_json = json.dumps(page_search_data, ensure_ascii=False)
        search_js = SEARCH_JS_TEMPLATE.replace('__SEARCH_DATA_JSON__', search_data_json).replace('$root', root_path)
        search_ui = SEARCH_UI_TEMPLATE.replace('$root', root_path)
        search_section = search_ui + search_js

    home_button = HOME_BUTTON_TEMPLATE.format(root_path) if category else ''

    return (
        PRE_HEADER +
        RSS_LINK.format(root_path, title) +
        HEADER_TEMPLATE.replace('$root', root_path) +
        TOGGLE_COLOR_SCHEME_JS +
        make_twitter_card(title, global_config) +
        TOC_TITLE_TEMPLATE.format(title) +
        home_button +
        make_categories_header(all_categories, root_path) +
        search_section +
        TOC_START +
        ''.join(toc_items) +
        TOC_END
    )


try:
    import lunr
    LUNR_AVAILABLE = True
except ImportError:
    LUNR_AVAILABLE = False


if __name__ == '__main__':
    global_config = extract_metadata(open('config.md', encoding='utf-8'))

    if '--sync' in sys.argv:
        subprocess.run(['rsync', '-av', 'site/.', '{}:{}'.format(global_config['server'], global_config['website_root'])])
        sys.exit()

    def process_post_file(file_location):
        filename = os.path.split(file_location)[1]
        print("Processing file: {}".format(filename))

        with open(file_location, encoding='utf-8') as f:
            metadata = extract_metadata(f, filename)
            body_content = f.read()

        root_path = '../../../..'                          # <-- 위로 옮김
        body_content = fix_math_setext_conflicts(body_content)
        body_content = fix_image_paths(body_content, root_path)   # <-- 추가

        path = metadata_to_path(global_config, metadata)
        options = metadata.get('pandoc', '')

        pandoc_extensions = (
            'gfm'
            '+tex_math_dollars'
            '+definition_lists'
            '+superscript'
            '+subscript'
            '+attributes'
            '+smart'
        )
        cmd = [
            'pandoc', '-f', pandoc_extensions, '-t', 'html',
            '--mathjax', '--wrap=preserve', '--highlight-style=pygments',
        ] + shlex.split(options)

        result = subprocess.run(cmd, input=body_content, capture_output=True, text=True, encoding='utf-8')
        pandoc_output = result.stdout

        total_file_contents = ''.join((
            PRE_HEADER,
            RSS_LINK.format(root_path, metadata['title']),
            HEADER_TEMPLATE.replace('$root', root_path),
            TOGGLE_COLOR_SCHEME_JS,
            make_twitter_card(metadata['title'], global_config),
            TITLE_TEMPLATE.format(metadata['title'], get_printed_date(metadata), root_path),
            defancify(pandoc_output),
            FOOTER,
        ))

        print("Path selected: {}".format(path))

        truncated_path = os.path.split(path)[0]
        os.makedirs(os.path.join('site', truncated_path), exist_ok=True)

        out_location = os.path.join('site', path)
        with open(out_location, 'w', encoding='utf-8') as out_f:
            out_f.write(total_file_contents)

    with ThreadPoolExecutor() as ex:
        list(ex.map(process_post_file, sys.argv[1:]))

    def load_post_metadata(filename):
        with open(os.path.join('posts', filename), encoding='utf-8') as f:
            return extract_metadata(f, filename)

    post_filenames = [
        entry.name for entry in os.scandir('posts')
        if entry.is_file() and entry.name[-4:-1] != '.sw'
    ]

    with ThreadPoolExecutor() as ex:
        metadatas = list(ex.map(load_post_metadata, post_filenames))

    categories = set(itertools.chain.from_iterable(m['categories'] for m in metadatas))
    categories = sorted(categories, key=lambda c: (c != '일반', c))

    print("Detected categories: {}".format(' '.join(categories)))

    sorted_metadatas = sorted(metadatas, key=lambda x: (x['date'], get_order(x)), reverse=True)
    feed = generate_feed(global_config, sorted_metadatas)

    search_index_data = generate_search_index(global_config, sorted_metadatas)

    os.makedirs(os.path.join('site', 'categories'), exist_ok=True)

    print("Building tables of contents...")

    homepage_cat = global_config.get('homepage_category', '')
    homepage_toc_items = []
    category_groups = defaultdict(list)
    for metadata in sorted_metadatas:
        cats = metadata['categories']
        if homepage_cat == '' or homepage_cat in cats:
            homepage_toc_items.append(make_toc_item(global_config, metadata, '.'))
        for c in cats:
            category_groups[c].append(make_toc_item(global_config, metadata, '..'))

    def write_category_page(category):
        toc = make_toc(
            category_groups.get(category, []), global_config, categories, category,
            include_search=True, search_index_data=search_index_data
        )
        with open(os.path.join('site', 'categories', category + '.html'), 'w', encoding='utf-8') as f:
            f.write(toc)

    with ThreadPoolExecutor() as ex:
        list(ex.map(write_category_page, categories))

    with open('site/feed.xml', 'w', encoding='utf-8') as f:
        f.write(feed)

    with open('site/index.html', 'w', encoding='utf-8') as f:
        f.write(make_toc(homepage_toc_items, global_config, categories, include_search=True, search_index_data=search_index_data))

    this_file_directory = os.path.dirname(__file__)
    shutil.copytree(os.path.join(this_file_directory, 'css'), 'site/css', dirs_exist_ok=True)
    shutil.copytree(os.path.join(this_file_directory, 'scripts'), 'site/scripts', dirs_exist_ok=True)

    search_css_path = os.path.join(this_file_directory, 'search-ui.css')
    if os.path.exists(search_css_path):
        shutil.copy(search_css_path, os.path.join('site', 'css', 'search-ui.css'))

    result = subprocess.run(['pandoc', '--print-highlight-style', 'pygments'], capture_output=True, text=True)
    with open(os.path.join('site', 'css', 'pandoc-highlight.css'), 'w', encoding='utf-8') as f:
        f.write(result.stdout)

    subprocess.run(['rsync', '-av', 'images', 'site/'])

    print("\n" + "=" * 50)
    print("검색 기능 완성!")
    print("=" * 50)
    print("생성된 파일:")
    print("  - site/index.html (검색 기능 내장)")
    print("  - site/scripts/lunr.min.js (검색 라이브러리)")
    print("  - site/css/search-ui.css (검색 스타일)")
    print("\n사용법:")
    print("  site/index.html 파일을 브라우저에서 열기만 하면 됩니다!")
    print("  file:// 프로토콜에서도 작동합니다")
    print("=" * 50)