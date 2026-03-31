<?php
/** @var string $role */
/** @var string $activeNav */
$role = $role ?? 'chairman';
$activeNav = $activeNav ?? '';
$r = 'role=' . urlencode($role);
?>
<nav class="site-nav">
    <?php if (in_array($role, ['chairman', 'admin'], true)): ?>
        <a class="nav-link <?= $activeNav === 'dashboard' ? 'active' : '' ?>" href="chairman_dashboard.php?<?= htmlspecialchars($r) ?>">Сводка KPI</a>
        <a class="nav-link <?= $activeNav === 'cards' ? 'active' : '' ?>" href="cards_chairman.php?<?= htmlspecialchars($r) ?>">Таблица заявок</a>
    <?php endif; ?>
    <?php if ($role === 'foreman'): ?>
        <a class="nav-link <?= $activeNav === 'foreman_list' ? 'active' : '' ?>" href="foreman_requests.php?<?= htmlspecialchars($r) ?>">Мои заявки</a>
        <a class="nav-link <?= $activeNav === 'foreman_new' ? 'active' : '' ?>" href="foreman_new.php?<?= htmlspecialchars($r) ?>">Новая заявка</a>
    <?php endif; ?>
    <?php if ($role === 'pdo'): ?>
        <a class="nav-link <?= $activeNav === 'pdo_queue' ? 'active' : '' ?>" href="pdo_queue.php?<?= htmlspecialchars($r) ?>">Очередь ПДО</a>
    <?php endif; ?>
    <?php if ($role === 'procurement'): ?>
        <a class="nav-link <?= $activeNav === 'proc_queue' ? 'active' : '' ?>" href="proc_queue.php?<?= htmlspecialchars($r) ?>">Очередь закупки</a>
    <?php endif; ?>
    <?php if ($role === 'admin'): ?>
        <a class="nav-link <?= $activeNav === 'admin_users' ? 'active' : '' ?>" href="admin_users.php?<?= htmlspecialchars($r) ?>">Пользователи</a>
    <?php endif; ?>
    <a class="nav-link" href="request.php?code=IG-24&<?= htmlspecialchars($r) ?>">Карточка (пример)</a>
</nav>
