<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$role = $_GET['role'] ?? 'chairman';
$pageTitle = 'Таблица заявок — демо';
$activeNav = 'cards';

$requests = site_load_json('requests');
$users = site_load_json('users');

$jsonRequests = site_json_encode_for_js($requests);
$jsonUsers = site_json_encode_for_js($users);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="header-top">
                <div>
                    <div class="page-title">Заявки по объектам</div>
                    <div class="page-subtitle">Данные из <code>site/data/requests.json</code> + локальные правки демо</div>
                </div>
                <span class="badge"><span>●</span> Фильтры синхронизируются с адресной строкой</span>
            </div>
        </div>
        <div class="header-controls">
            <button type="button" class="btn-reset" id="resetFilters">Сбросить фильтры</button>
        </div>
    </div>

    <section class="filters">
        <div class="filter-group">
            <label class="filter-label" for="statusFilter">Статус</label>
            <select id="statusFilter" class="filter-select">
                <option value="">Все</option>
                <option value="waiting">Ждёт действия</option>
                <option value="in_progress">В работе</option>
                <option value="forwarded">Передано дальше</option>
                <option value="closed">Закрыто</option>
                <option value="cancelled">Отменено</option>
                <option value="paused">На паузе</option>
                <option value="terminated">Прекращено</option>
            </select>
        </div>
        <div class="filter-group">
            <label class="filter-label" for="stageFilter">Этап</label>
            <select id="stageFilter" class="filter-select">
                <option value="">Все</option>
                <option value="created">Создано</option>
                <option value="pdo_processing">ПДО в работе</option>
                <option value="transferred_to_procurement">Передано в закупку</option>
                <option value="procurement_in_work">Закупка в работе</option>
                <option value="purchased">Закуплено</option>
                <option value="shipped">Отгружено</option>
                <option value="partially_received">Получено частично</option>
                <option value="fully_received">Получено полностью</option>
            </select>
        </div>
        <div class="filter-group">
            <label class="filter-label" for="objectFilter">Объект</label>
            <input id="objectFilter" class="filter-input" placeholder="Например: Игора, Фундамент">
        </div>
        <div class="filter-group">
            <label class="filter-label" for="roleFilter">Ответственный</label>
            <select id="roleFilter" class="filter-select">
                <option value="">Все</option>
                <option value="foreman">Прораб</option>
                <option value="pdo">ПДО</option>
                <option value="procurement">Закупка</option>
                <option value="manager">Руководитель</option>
                <option value="viewer">Зритель</option>
            </select>
        </div>
        <div class="filter-group">
            <label class="filter-label" for="searchFilter">Поиск</label>
            <input id="searchFilter" class="filter-input" placeholder="Код, наименование, согласовано с...">
        </div>
    </section>

    <div class="chips">
        <span class="chip">Показаны заявки с учётом демо-слоя (localStorage)</span>
        <span class="chip" id="activeFiltersInfo">Активных фильтров: 0</span>
    </div>

    <div class="table-wrapper">
        <table>
            <thead>
            <tr>
                <th>ID заявки</th>
                <th>Статус / этап</th>
                <th>Объект / подобъект</th>
                <th>Наименование</th>
                <th>Кол-во</th>
                <th>Со склада / в закупку</th>
                <th>Получено / остаток</th>
                <th>Ответственный</th>
                <th>С кем согласовано</th>
                <th>Срок / создано</th>
            </tr>
            </thead>
            <tbody id="requestsBody"></tbody>
        </table>
    </div>

    <div class="counter" id="counter"></div>
<script type="application/json" id="site-data-requests"><?php echo $jsonRequests; ?></script>
<script type="application/json" id="site-data-users"><?php echo $jsonUsers; ?></script>
<?php
ob_start();
?>
<script>
(function () {
  var BASE_REQUESTS = JSON.parse(document.getElementById('site-data-requests').textContent);
  var USERS = JSON.parse(document.getElementById('site-data-users').textContent);

  function mergedList() {
    return window.StroikaDemo.mergeRequests(BASE_REQUESTS);
  }

  var statusFilter = document.getElementById('statusFilter');
  var stageFilter = document.getElementById('stageFilter');
  var objectFilter = document.getElementById('objectFilter');
  var roleFilter = document.getElementById('roleFilter');
  var searchFilter = document.getElementById('searchFilter');
  var resetBtn = document.getElementById('resetFilters');
  var tbody = document.getElementById('requestsBody');
  var counter = document.getElementById('counter');
  var activeFiltersInfo = document.getElementById('activeFiltersInfo');

  function readParams() {
    var p = new URLSearchParams(window.location.search);
    if (p.get('status')) statusFilter.value = p.get('status');
    if (p.get('stage')) stageFilter.value = p.get('stage');
    if (p.get('object')) objectFilter.value = p.get('object');
    if (p.get('resp')) roleFilter.value = p.get('resp');
    if (p.get('q')) searchFilter.value = p.get('q');
  }

  function writeParams() {
    var p = new URLSearchParams();
    var r = new URLSearchParams(window.location.search).get('role');
    if (r) p.set('role', r);
    if (statusFilter.value) p.set('status', statusFilter.value);
    if (stageFilter.value) p.set('stage', stageFilter.value);
    if (objectFilter.value.trim()) p.set('object', objectFilter.value.trim());
    if (roleFilter.value) p.set('resp', roleFilter.value);
    if (searchFilter.value.trim()) p.set('q', searchFilter.value.trim());
    var qs = p.toString();
    var url = window.location.pathname + (qs ? '?' + qs : '');
    window.history.replaceState({}, '', url);
  }

  function applyFilters() {
    var sStatus = statusFilter.value.trim();
    var sStage = stageFilter.value.trim();
    var sObj = objectFilter.value.trim().toLowerCase();
    var sRole = roleFilter.value.trim();
    var sSearch = searchFilter.value.trim().toLowerCase();

    var active = 0;
    if (sStatus) active++;
    if (sStage) active++;
    if (sObj) active++;
    if (sRole) active++;
    if (sSearch) active++;
    activeFiltersInfo.textContent = 'Активных фильтров: ' + active;

    var list = mergedList();
    var filtered = list.filter(function (r) {
      if (sStatus && r.status_code !== sStatus) return false;
      if (sStage && r.stage_code !== sStage) return false;
      if (sRole && r.responsible_role !== sRole) return false;
      if (sObj) {
        var hay = ((r.object_name || '') + ' ' + (r.subobject_name || '')).toLowerCase();
        if (hay.indexOf(sObj) === -1) return false;
      }
      if (sSearch) {
        var hay2 = [
          r.request_code,
          r.name_from_foreman,
          r.nomenclature_1c,
          r.code_1c,
          r.approved_by,
        ].join(' ').toLowerCase();
        if (hay2.indexOf(sSearch) === -1) return false;
      }
      return true;
    });

    tbody.innerHTML = filtered.map(function (r) {
      return window.StroikaFmt.renderTableRow(r, USERS);
    }).join('');
    counter.textContent = 'Показано ' + filtered.length + ' из ' + list.length + ' заявок';
    writeParams();
  }

  statusFilter.addEventListener('change', applyFilters);
  stageFilter.addEventListener('change', applyFilters);
  objectFilter.addEventListener('input', applyFilters);
  roleFilter.addEventListener('change', applyFilters);
  searchFilter.addEventListener('input', applyFilters);

  resetBtn.addEventListener('click', function () {
    statusFilter.value = '';
    stageFilter.value = '';
    objectFilter.value = '';
    roleFilter.value = '';
    searchFilter.value = '';
    applyFilters();
  });

  readParams();
  applyFilters();
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
