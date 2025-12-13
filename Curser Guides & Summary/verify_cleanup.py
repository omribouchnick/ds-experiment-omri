"""
Verify cleanup - check that TOAST responses match completions
Run: python manage.py shell < verify_cleanup.py
"""

from experiment.models import ExperimentData, ExperimentAction, TOASTResponse
from django.db.models import Count

print("=" * 60)
print("VERIFICATION AFTER CLEANUP")
print("=" * 60)

total_users = ExperimentData.objects.count()
completed = ExperimentData.objects.filter(complete=True).count()
total_toast = TOASTResponse.objects.count()

print(f"\n📊 Summary:")
print(f"   Total Users: {total_users}")
print(f"   ✅ Completed: {completed}")
print(f"   📋 TOAST Responses: {total_toast}")
print(f"   Difference: {total_toast - completed}")

# Check for any remaining duplicates
print("\n" + "=" * 60)
print("Checking for any remaining duplicate TOAST responses:")
print("=" * 60)
duplicates = TOASTResponse.objects.values('user_id').annotate(count=Count('user_id')).filter(count__gt=1)
if duplicates:
    print("   ⚠️  Found duplicates:")
    for dup in duplicates:
        user_id = dup['user_id']
        count = dup['count']
        print(f"      User {user_id}: {count} TOAST responses")
else:
    print("   ✅ No duplicates found - all users have at most 1 TOAST response")

# Verify User 81
print("\n" + "=" * 60)
print("User 81 verification:")
print("=" * 60)
user81_toast = TOASTResponse.objects.filter(user_id=81).count()
print(f"   TOAST responses for User 81: {user81_toast} (should be 1)")

# Final status
print("\n" + "=" * 60)
print("✅ CLEANUP VERIFICATION COMPLETE")
print("=" * 60)
exit()


