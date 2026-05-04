// Badges that have no image / were retired but may still appear in API responses.
// Filter these out everywhere badges are rendered.
export const HIDDEN_BADGE_IDS = new Set<string>(
  [
    'A1B2C3D4-E5F6-7890-ABCD-EF1234567890', // Coin Collector
    'B2C3D4E5-F6A7-8901-BCDE-F12345678901', // Button Box
    'C3D4E5F6-A7B8-9012-CDEF-123456789012', // Lead Farmer
    'D4E5F6A7-B8C9-0123-DEF0-234567890123', // Jewelry Box
    '79F9EB4B-7278-4905-B46F-3FD4696778D5', // Buckle Bonanza (imageless)
  ].map((s) => s.toLowerCase()),
);

export function isHiddenBadge(badgeId: string): boolean {
  return HIDDEN_BADGE_IDS.has(badgeId.toLowerCase());
}
