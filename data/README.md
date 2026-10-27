# Synthetic Retail Dataset

The generated CSV files in `data/synthetic_retail/` are synthetic and deterministic. They exist only for the EvidenceTrail AI demo and tests.

Known scenarios:

1. **September 2025 revenue decline:** aggregate revenue is lower than August, concentrated in Trail Running Shoes and a small number of products.
2. **Repeated availability disruption:** Trail Running Shoes records repeated stockout days, low ending inventory, and Northstar Outfitters delivery delays in August–October 2025.
3. **Pricing association:** Trail Running Shoes and Hiking Backpack have price changes that coincide with lower units in selected months. This is intentionally an association, not proof of price causality.
4. **Seasonality:** November and December demand is higher than the early-year baseline.
5. **Supplier disruption:** supplier delay records connect affected purchase orders to availability signals.

Regenerate with:

```bash
cd backend
python -m app.data.seed
```
