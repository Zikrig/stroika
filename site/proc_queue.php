<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$role = $_GET['role'] ?? 'procurement';
$pageTitle = 'Очередь закупки — демо';
$activeNav = 'proc_queue';

$requests = site_load_json('requests');
$jsonRequests = site_json_encode_for_js($requests);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Очередь закупки</div>
            <p class="page-subtitle">Этапы: передано в закупку, закупка в работе, закуплено</p>
        </div>
    </div>

    <div class="table-wrapper">
        <table>
            <thead>
            <tr>
                <th>Код</th>
                <th>Этап</th>
                <th>Объект</th>
                <th>В закупку</th>
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
  var role = new URLSearchParams(location.search).get('role') || 'procurement';

  function render() {
    var list = window.StroikaDemo.mergeRequests(BASE).filter(function (r) {
      var s = r.stage_code;
      return (
        ['transferred_to_procurement', 'procurement_in_work', 'purchased'].indexOf(s) >= 0 && !r.is_container
      );
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
          f.fmtQty(r.to_purchase_qty) +
          '</td><td><a class="link-code" href="proc_request.php?code=' +
          encodeURIComponent(r.request_code) +
          '&role=' +
          encodeURIComponent(role) +
          '">Действия</a></td></tr>'
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
