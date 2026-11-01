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

## 8. External Load Operations

The application architecture must support future external-load operations.

Supported load types:
- Sling loads
- Longline operations
- Underslung cargo
- Cargo nets

The system must accommodate:
- External load weights
- Sling and equipment weights
- Attachment configurations
- Aircraft-specific limitations
- Approved performance data
- Load configuration records

External-load calculations will be developed as a separate module.

## 9. Engine Configurations and Modifications

Aircraft variants must support different approved engine
configurations where applicable.

Individual aircraft profiles must record:
- Installed engine model
- Engine serial number
- Approved modifications
- Installed equipment
- Applicable flight manual supplements
- Configuration references

Configuration changes must trigger appropriate validation.

## 10. Aircraft Profile Version Control

Every aircraft profile must maintain a revision history.

Each revision must record:
- Revision number
- Timestamp
- Changed fields
- Previous values
- New values
- Change description
- Reason for change

Required functionality:
- View revision history
- Compare revisions
- Restore previous revisions
- Preserve historical revisions
- Create a new revision when restoring an old revision

Historical flight records must retain the exact aircraft
configuration and technical data used during that flight.

Aircraft profile changes must never silently alter
previously completed flight records.

Revision history should be implemented using database
snapshots and change records.

## 11. Authentication and Permissions

Authentication and role-based permissions are explicitly
excluded from the initial development scope.

The initial application will operate without:
- User login
- User accounts
- Administrator roles
- Permission restrictions
- Role-based access control

Change history and data integrity remain mandatory.

The architecture should allow authentication and permissions
to be introduced in a future development phase.
