<?php
$extraScripts = $extraScripts ?? '';
?>
</div>
<script src="assets/app.js"></script>
<?php if ($extraScripts !== ''): ?>
<?= $extraScripts ?>
<?php endif; ?>
</body>
</html>
