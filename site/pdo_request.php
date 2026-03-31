<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$code = $_GET['code'] ?? 'IG-25';
$role = $_GET['role'] ?? 'pdo';
$pageTitle = 'ПДО: ' . $code;

$requests = site_load_json('requests');
$jsonRequests = site_json_encode_for_js($requests);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Обработка заявки ПДО</div>
            <p class="page-subtitle">Демо-действия пишутся в localStorage</p>
        </div>
    </div>

    <div class="request-detail" id="box">
        <p id="line1"></p>
        <p class="muted" id="line2"></p>
        <button type="button" class="btn-primary" id="btnTake">Взять в работу</button>
        <button type="button" class="btn-secondary" id="btnSplit">Имитировать дробление (2 строки)</button>
        <p class="muted" id="hint"></p>
    </div>
<?php
ob_start();
?>
<script>
(function () {
  var BASE = <?= $jsonRequests ?>;
  var CODE = <?= json_encode($code, JSON_UNESCAPED_UNICODE) ?: '""' ?>;

  function find() {
    var list = window.StroikaDemo.mergeRequests(BASE);
    for (var i = 0; i < list.length; i++) {
      if (list[i].request_code === CODE) return list[i];
    }
    return null;
  }

  function render() {
    var r = find();
    if (!r) {
      document.getElementById('line1').textContent = 'Заявка не найдена';
      return;
    }
    document.getElementById('line1').innerHTML =
      '<strong>' + window.StroikaFmt.escapeHtml(r.request_code) + '</strong> — ' +
      window.StroikaFmt.escapeHtml(r.name_from_foreman || '');
    document.getElementById('line2').textContent = 'Этап: ' + (r.stage_code || '');
  }

  document.getElementById('btnTake').addEventListener('click', function () {
    var r = find();
    if (!r) return;
    window.StroikaDemo.patchRequest(r.id, {
      status_code: 'in_progress',
      stage_code: 'pdo_processing',
      responsible_role: 'pdo',
    });
    window.StroikaDemo.addEvent({
      id: 'demo-pdo-taken-' + Date.now(),
      request_id: r.id,
      event_type: 'pdo_taken',
      actor_user_id: 20,
      actor_role: 'pdo',
      payload_json: {},
      created_at: new Date().toISOString(),
    });
    document.getElementById('hint').textContent = 'Взято в работу (демо).';
    render();
  });

  document.getElementById('btnSplit').addEventListener('click', function () {
    var r = find();
    if (!r) return;
    var parentId = r.id;
    var baseCode = r.request_code;
    window.StroikaDemo.patchRequest(parentId, {
      status_code: 'closed',
      stage_code: 'fully_received',
      is_container: 1,
      responsible_role: null,
      remaining_qty: 0,
      nomenclature_1c: '—',
    });
    window.StroikaDemo.addEvent({
      id: 'demo-split-' + Date.now(),
      request_id: parentId,
      event_type: 'pdo_formalized',
      actor_user_id: 20,
      actor_role: 'pdo',
      payload_json: { mode: 'container', children_count: 2 },
      created_at: new Date().toISOString(),
    });

    var c1 = baseCode + '-1';
    var c2 = baseCode + '-2';
    var id1 = 'demo-child-' + Date.now() + '-1';
    var id2 = 'demo-child-' + Date.now() + '-2';
    window.StroikaDemo.addRequest({
      id: id1,
      request_code: c1,
      chat_id: r.chat_id,
      parent_request_id: parentId,
      is_container: 0,
      foreman_user_id: r.foreman_user_id,
      object_name: r.object_name,
      subobject_name: r.subobject_name,
      name_from_foreman: (r.name_from_foreman || '') + ' (часть 1)',
      nomenclature_1c: r.nomenclature_1c || 'Позиция 1',
      code_1c: 'D1',
      requested_qty: 50,
      unit: r.unit || 'шт',
      from_stock_qty: 10,
      to_purchase_qty: 40,
      received_total_qty: 0,
      remaining_qty: 50,
      status_code: 'waiting',
      stage_code: 'transferred_to_procurement',
      responsible_role: 'procurement',
      approved_by: r.approved_by,
      need_by: r.need_by,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    window.StroikaDemo.addRequest({
      id: id2,
      request_code: c2,
      chat_id: r.chat_id,
      parent_request_id: parentId,
      is_container: 0,
      foreman_user_id: r.foreman_user_id,
      object_name: r.object_name,
      subobject_name: r.subobject_name,
      name_from_foreman: (r.name_from_foreman || '') + ' (часть 2)',
      nomenclature_1c: r.nomenclature_1c || 'Позиция 2',
      code_1c: 'D2',
      requested_qty: 30,
      unit: r.unit || 'шт',
      from_stock_qty: 30,
      to_purchase_qty: 0,
      received_total_qty: 0,
      remaining_qty: 30,
      status_code: 'forwarded',
      stage_code: 'shipped',
      responsible_role: 'foreman',
      approved_by: r.approved_by,
      need_by: r.need_by,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    document.getElementById('hint').innerHTML =
      'Контейнер закрыт, добавлены <a href="request.php?code=' +
      encodeURIComponent(c1) +
      '">' +
      c1 +
      '</a> и <a href="request.php?code=' +
      encodeURIComponent(c2) +
      '">' +
      c2 +
      '</a>.';
  });

  render();
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
