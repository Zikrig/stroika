<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$role = $_GET['role'] ?? 'chairman';
$pageTitle = 'Сводка KPI — демо';
$activeNav = 'dashboard';

$requests = site_load_json('requests');
$jsonRequests = site_json_encode_for_js($requests);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Сводка по заявкам</div>
            <p class="page-subtitle">Показатели считаются в браузере по объединённым данным (JSON + демо-слой)</p>
        </div>
    </div>

    <div class="kpi-grid" id="kpiGrid">
        <div class="kpi-card">
            <div class="kpi-value" id="kpiActive">—</div>
            <div class="kpi-label">Активных (не закрыты / не отменены)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value" id="kpiOverdue">—</div>
            <div class="kpi-label">Просрочка по сроку need_by</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value" id="kpiPaused">—</div>
            <div class="kpi-label">На паузе</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value" id="kpiProc">—</div>
            <div class="kpi-label">В закупке (этап закупки)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value" id="kpiContainers">—</div>
            <div class="kpi-label">Контейнеры (дробление)</div>
        </div>
    </div>

    <p class="muted"><a href="cards_chairman.php?role=<?= htmlspecialchars(urlencode($role), ENT_QUOTES, 'UTF-8') ?>">Открыть таблицу заявок</a></p>
<?php
ob_start();
?>
<script>
(function () {
  var BASE = <?= $jsonRequests ?>;

  function todayStr() {
    var d = new Date();
    return d.toISOString().slice(0, 10);
  }

  function isClosed(r) {
    return ['closed', 'cancelled', 'terminated'].indexOf(r.status_code) >= 0;
  }

  function isProcurementStage(r) {
    var s = r.stage_code || '';
    return ['transferred_to_procurement', 'procurement_in_work', 'purchased'].indexOf(s) >= 0;
  }

  function refresh() {
    var list = window.StroikaDemo.mergeRequests(BASE);
    var active = 0, overdue = 0, paused = 0, proc = 0, containers = 0;
    var t = todayStr();
    list.forEach(function (r) {
      if (r.is_container) containers++;
      if (r.status_code === 'paused' || r.stage_code === 'paused') paused++;
      if (!isClosed(r)) {
        active++;
        var nb = (r.need_by || '').slice(0, 10);
        if (nb && nb < t) overdue++;
        if (isProcurementStage(r) && !isClosed(r)) proc++;
      }
    });
    document.getElementById('kpiActive').textContent = String(active);
    document.getElementById('kpiOverdue').textContent = String(overdue);
    document.getElementById('kpiPaused').textContent = String(paused);
    document.getElementById('kpiProc').textContent = String(proc);
    document.getElementById('kpiContainers').textContent = String(containers);
  }

  refresh();
  window.addEventListener('storage', function () {
    refresh();
  });
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
