from store import store_kpi_metrics
try:
    store_kpi_metrics([{'period':'','category':'github','metric':'opened','value':0.0,'unit':None,'confidence':0.9,'source':'github'}])
    print("Store OK")
except Exception as e:
    import logging; logging.error(f'Error: {e}', exc_info=True)
    print(f"Store fail: {type(e).__name__}: {e}")
