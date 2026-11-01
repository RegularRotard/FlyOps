# FlightOps Manager - Aircraft Architecture

## 1. Design Principle

The application must support multiple helicopter manufacturers,
families, variants and individual aircraft.

Aircraft-specific calculations must never rely on generic
manufacturer or family-level assumptions.

## 2. Aircraft Hierarchy

1. Manufacturer
2. Aircraft Family
3. Aircraft Variant
4. Individual Aircraft Profile

## 3. Initial Aircraft Families

### Robinson Helicopter Company
- R22
- R44
  - Raven I
  - Raven II
  - Clipper variants

### Airbus Helicopters
- AS350
  - B
  - BA
  - B2
  - B3
  - B3e
- H125

### Guimbal
- Cabri G2

This list is an initial development list, not an exhaustive
aircraft catalogue.

## 4. Individual Aircraft Profile

Each aircraft must support:

- Registration
- Manufacturer
- Model
- Variant
- Serial number
- Engine configuration
- Installed equipment
- Seating configuration
- Fuel configuration
- Basic empty weight
- Empty weight centre of gravity
- Weight and balance document reference
- Flight manual reference
- Applicable supplements
- Document revision information

## 5. Aircraft Technical Data

Each variant must support configurable:

- Maximum take-off weight
- Maximum landing weight, where applicable
- Longitudinal CG envelope
- Lateral CG envelope, where applicable
- Fuel capacity
- Fuel tank arms
- Seat positions and arms
- Baggage compartment positions and limits
- Engine limitations
- Transmission limitations
- Performance data
- Operating limitations

## 6. Data Integrity

- Aircraft data must be traceable to approved documentation.
- Variant-specific data must not be interchangeable by default.
- Individual aircraft configurations must be independently maintained.
- Changes must preserve historical records.
- Technical data must include source and revision references.
- Unverified technical data must never be treated as approved.
- Missing critical data must prevent operational release.

## 7. Future Requirements

- Multiple engine configurations.
- Optional equipment and modifications.
- Aircraft-specific supplements.
- External load configurations.
- Performance calculations.
- Version-controlled weight and balance data.
- Aircraft utilisation and maintenance records.
