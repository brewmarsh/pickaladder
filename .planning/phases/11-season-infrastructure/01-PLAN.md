# Plan: 11-01: Season Data Model & CRUD

**Goal:** Establish the underlying data structure and basic management for recurring tournament seasons.

## Tasks
1. [ ] Define the `Season` schema:
    - `name`: e.g., "Spring 2026".
    - `groupId`: Reference to the parent group.
    - `startDate`, `endDate`.
    - `status`: DRAFT, ACTIVE, COMPLETED.
    - `divisionIds`: Optional list of sub-division references.
2. [ ] Create `pickaladder/season/` blueprint.
3. [ ] Implement `SeasonRepository` and `SeasonService` for basic CRUD.
4. [ ] Add UI for Group Owners to create/manage Seasons.
5. [ ] Update Navigation to include a "Seasons" link within Groups.

## Technical Details
- **Firestore Path:** `/groups/{gid}/seasons/{sid}` or a root `/seasons` collection with `groupId` index. Prefer root collection for easier cross-group reporting later.
- **Rules:** Only group admins can create/edit seasons.

## Success Criteria
- [ ] Group owners can create a new Season.
- [ ] Seasons are visible in the Group view.
- [ ] Basic unit tests for CRUD operations.
