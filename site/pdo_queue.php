<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$role = $_GET['role'] ?? 'pdo';
$pageTitle = 'Очередь ПДО — демо';
$activeNav = 'pdo_queue';

$requests = site_load_json('requests');
$jsonRequests = site_json_encode_for_js($requests);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Очередь ПДО</div>
            <p class="page-subtitle">Этапы: <code>created</code>, <code>pdo_processing</code></p>
        </div>
    </div>

    <div class="table-wrapper">
        <table>
            <thead>
            <tr>
                <th>Код</th>
                <th>Этап</th>
                <th>Объект</th>
                <th>Наименование</th>
                <th></th>
            </tr>
            </thead>
            <tbody id="tbody"></tbody>
        </table>
    </div>
<?php
ob_start();
?>
<script>
(function () {
  var BASE = <?= $jsonRequests ?>;
  var f = window.StroikaFmt;
  var role = new URLSearchParams(location.search).get('role') || 'pdo';

  function render() {
    var list = window.StroikaDemo.mergeRequests(BASE).filter(function (r) {
      var s = r.stage_code;
      return (s === 'created' || s === 'pdo_processing') && !r.is_container;
    });
    document.getElementById('tbody').innerHTML = list
      .map(function (r) {
        return (
          '<tr><td>' +
          f.escapeHtml(r.request_code) +
          '</td><td>' +
          f.formatStage(r.stage_code) +
          '</td><td>' +
          f.escapeHtml(r.object_name || '') +
          '</td><td>' +
          f.escapeHtml(r.nomenclature_1c || r.name_from_foreman || '') +
          '</td><td><a class="link-code" href="pdo_request.php?code=' +
          encodeURIComponent(r.request_code) +
          '&role=' +
          encodeURIComponent(role) +
          '">Открыть</a></td></tr>'
        );
      })
      .join('') || '<tr><td colspan="5" class="muted">Пусто</td></tr>';
  }
  render();
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
