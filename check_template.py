content = open('templates/solar/design_result.html', encoding='utf-8').read()
checks = [
    ('Solar generator in Design Validation', 'solar_generator_option' in content),
    ('Warnings accordion with count badge', 'warnings-count' in content),
    ('Accordion collapse markup', 'accordion' in content.lower()),
    ('Material/transport/install pricing rows', all(x in content for x in ['price-material','price-transport','price-installation'])),
    ('Parameter Required Selected columns', all(x in content for x in ['Required Capacity','Selected Component'])),
    ('Power column in appliances', 'Power' in content),
    ('fadeInUp CSS animation', 'fadeInUp' in content),
    ('KWH KVA units present', 'KWH' in content and 'KVA' in content),
    ('Horizontal scroll table-responsive', 'table-responsive' in content or 'overflow-x' in content),
    ('BOQ Unit Price and Total columns', 'Unit Price' in content and 'Total' in content),
    ('NO component available fallback', 'NO ' in content and 'available' in content),
    ('Series Parallel row', 'Series' in content and 'Parallel' in content),
]
for name, result in checks:
    status = 'PASS' if result else 'FAIL'
    print(f'  [{status}] {name}')
