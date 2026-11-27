/* Book transfer page: export selection, download, and upload-based import. */
(function () {
  const root = document.getElementById('book-transfer');
  if (!root) return;
  const token = root.dataset.token;
  const message = document.getElementById('transfer-message');
  const progress = document.getElementById('transfer-progress');
  const books = Array.from(root.querySelectorAll('[data-book]'));
  const selectAll = document.getElementById('transfer-all');
  const none = document.getElementById('transfer-none');
  const exportButton = document.getElementById('transfer-export');
  const count = document.getElementById('transfer-count');
  const fileInput = document.getElementById('transfer-file');
  const inspectButton = document.getElementById('transfer-inspect');
  const importButton = document.getElementById('transfer-import');
  const replace = document.getElementById('transfer-replace');
  const missing = document.getElementById('transfer-missing');
  const result = document.getElementById('transfer-result');
  const packSize = document.getElementById('transfer-size');
  let busy = false;

  function selected() {
    return books.filter(box => box.checked).map(box => box.value);
  }

  function refresh() {
    const chosen = selected();
    count.textContent = chosen.length
      ? 'Избрани: ' + chosen.length + ' от ' + books.length
      : 'Не е избран нито един учебник';
    exportButton.disabled = busy || chosen.length === 0;
  }

  if (selectAll) selectAll.addEventListener('click', () => {
    books.forEach(box => { box.checked = true; });
    refresh();
  });
  if (none) none.addEventListener('click', () => {
    books.forEach(box => { box.checked = false; });
    refresh();
  });
  books.forEach(box => box.addEventListener('change', refresh));
  refresh();

  function setBusy(state, text) {
    busy = state;
    if (text !== undefined) progress.textContent = text;
    refresh();
    [inspectButton, importButton].forEach(button => { if (button) button.disabled = state; });
  }

  exportButton.addEventListener('click', () => {
    const chosen = selected();
    if (!chosen.length) return;
    setBusy(true, 'Създаване на пакета…');
    message.textContent = '';
    const params = new URLSearchParams();
    params.set('books', chosen.join(','));
    if (missing && missing.checked) params.set('allow_missing', '1');
    const frame = document.createElement('iframe');
    frame.hidden = true;
    frame.src = '/__transfer__/download?' + params.toString();
    document.body.appendChild(frame);
    setTimeout(() => {
      setBusy(false, 'Пакетът се изтегля от браузъра. Ако не се появи файл, виж съобщението над бутоните.');
    }, 1200);
  });

  fileInput.addEventListener('change', () => {
    const file = fileInput.files && fileInput.files[0];
    if (packSize) packSize.textContent = file
      ? 'Избран файл: ' + file.name + ' · ' + (file.size / 1048576).toFixed(1) + ' MB'
      : '';
    result.textContent = '';
    result.hidden = true;
  });

  function upload(target) {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      message.textContent = 'Избери ZIP файл, преди да продължиш.';
      return;
    }
    const params = new URLSearchParams();
    params.set('filename', file.name);
    if (replace && replace.checked) params.set('replace', '1');
    if (target === 'import') {
      setBusy(true, 'Копиране на файловете… Това може да отнеме няколко минути за големи учебници.');
    } else {
      setBusy(true, 'Проверка на пакета…');
    }
    message.textContent = '';
    const request = new XMLHttpRequest();
    request.open('POST', '/__transfer__/' + target + '?' + params.toString());
    request.setRequestHeader('Content-Type', 'application/octet-stream');
    request.setRequestHeader('X-IZZI-Control', token);
    request.upload.onprogress = event => {
      if (event.lengthComputable) {
        progress.textContent = 'Изпращане: ' + Math.round(event.loaded / event.total * 100) + '%' +
          (target === 'import' ? ' · после файловете се копират на диска' : '');
      }
    };
    request.onload = () => {
      let data = null;
      try { data = JSON.parse(request.responseText); } catch (error) { data = null; }
      if (request.status !== 200 || !data) {
        setBusy(false, 'Спиране');
        message.textContent = (data && data.error) || ('Грешка при ' + target + ' (HTTP ' + request.status + ')');
        return;
      }
      setBusy(false, 'Готово.');
      render(target, data);
    };
    request.onerror = () => {
      setBusy(false, 'Спиране');
      message.textContent = 'Връзката със сървъра беше прекъсната.';
    };
    request.send(file);
  }

  function line(text) {
    const p = document.createElement('p');
    p.textContent = text;
    return p;
  }

  function render(target, data) {
    result.textContent = '';
    result.hidden = false;
    if (target === 'inspect') {
      result.appendChild(line('Пакетът съдържа:'));
      Object.keys(data.books || {}).forEach(id => {
        result.appendChild(line('  ' + id + ' — ' + data.books[id]));
      });
      if (data.adding && data.adding.length) result.appendChild(line('Нови учебници: ' + data.adding.join(', ')));
      if (data.replacing && data.replacing.length) result.appendChild(line('Вече са налични: ' + data.replacing.join(', ') + ' (нужно е „Обнови съществуващите“)'));
      result.appendChild(line('Архивни файлове: ' + data.files_new + ' нови, ' + data.files_present + ' вече налични'));
      result.appendChild(line('URL записи: ' + data.URLs_new + ' нови, ' + data.URLs_replaced + ' презаписани'));
      if (data.conflicts && data.conflicts.length) {
        result.appendChild(line('Конфликти: ' + data.conflicts.length + ' файла с различен размер на тази машина'));
        data.conflicts.slice(0, 10).forEach(key => result.appendChild(line('  ' + key)));
        message.textContent = 'Импортът ще бъде отказан, докато конфликтните файлове не се преместят.';
      } else {
        message.textContent = 'Пакетът е валиден. Можеш да го внесеш.';
      }
      return;
    }
    result.appendChild(line('Внесени учебници: ' + Object.keys(data.books || {}).join(', ')));
    result.appendChild(line('Архивни файлове: ' + data.copied + ' копирани, ' + data.restored + ' вече налични'));
    result.appendChild(line('URL записи: ' + data.URLs + ' слети в индекса'));
    message.textContent = 'Импортът завърши. Рестартирай библиотеката, за да се презаредят индексите.';
  }

  if (inspectButton) inspectButton.addEventListener('click', () => upload('inspect'));
  if (importButton) importButton.addEventListener('click', () => {
    if (confirm('Да внеса ли избрания пакет в тази инсталация? Съществуващите учебници извън пакета остават непокътнати.')) upload('import');
  });
})();
