"""
Investigate TOAST responses vs completions
Run: python manage.py shell < investigate_toast_mismatch.py
Or copy-paste into Django shell
"""

from experiment.models import ExperimentData, ExperimentAction, TOASTResponse

print("=" * 60)
print("INVESTIGATING TOAST RESPONSES vs COMPLETIONS")
print("=" * 60)

total_users = ExperimentData.objects.count()
completed = ExperimentData.objects.filter(complete=True).count()
total_toast = TOASTResponse.objects.count()

print(f"\n📊 Summary:")
print(f"   Total Users: {total_users}")
print(f"   ✅ Completed: {completed}")
print(f"   📋 TOAST Responses: {total_toast}")
print(f"   Difference: {total_toast - completed}")

# Check for users with TOAST but incomplete
print("\n" + "=" * 60)
print("Users with TOAST responses but INCOMPLETE status:")
print("=" * 60)
incomplete_with_toast = []
for user in ExperimentData.objects.filter(complete=False):
    if TOASTResponse.objects.filter(user_id=user.user_id).exists():
        toast = TOASTResponse.objects.get(user_id=user.user_id)
        actions = ExperimentAction.objects.filter(user_id=user.user_id).count()
        incomplete_with_toast.append({
            'user_id': user.user_id,
            'aid': user.aid,
            'actions': actions,
            'has_toast': True
        })
        print(f"   User {user.user_id} (AID: {user.aid}): {actions}/120 actions, has TOAST")

if not incomplete_with_toast:
    print("   None found")

# Check for duplicate TOAST responses (same user_id)
print("\n" + "=" * 60)
print("Checking for duplicate TOAST responses (same user_id):")
print("=" * 60)
from django.db.models import Count
duplicates = TOASTResponse.objects.values('user_id').annotate(count=Count('user_id')).filter(count__gt=1)
if duplicates:
    for dup in duplicates:
        user_id = dup['user_id']
        count = dup['count']
        print(f"   User {user_id}: {count} TOAST responses")
        for toast in TOASTResponse.objects.filter(user_id=user_id):
            print(f"      - ID: {toast.id}, created: {toast.user_id.start_time if hasattr(toast, 'user_id') else 'N/A'}")
else:
    print("   No duplicates found")

# Check users with TOAST but less than 120 actions
print("\n" + "=" * 60)
print("Users with TOAST but < 120 actions:")
print("=" * 60)
for toast in TOASTResponse.objects.all():
    user_id = toast.user_id.user_id
    actions = ExperimentAction.objects.filter(user_id=user_id).count()
    user_data = ExperimentData.objects.get(user_id=user_id)
    if actions < 120:
        print(f"   User {user_id}: {actions}/120 actions, Complete: {user_data.complete}, AID: {user_data.aid}")

# Summary by completion status
print("\n" + "=" * 60)
print("TOAST responses by user completion status:")
print("=" * 60)
completed_users = ExperimentData.objects.filter(complete=True)
incomplete_users = ExperimentData.objects.filter(complete=False)

completed_with_toast = sum(1 for u in completed_users if TOASTResponse.objects.filter(user_id=u.user_id).exists())
incomplete_with_toast = sum(1 for u in incomplete_users if TOASTResponse.objects.filter(user_id=u.user_id).exists())

print(f"   Completed users with TOAST: {completed_with_toast}")
print(f"   Incomplete users with TOAST: {incomplete_with_toast}")
print(f"   Total TOAST responses: {total_toast}")

print("\n" + "=" * 60)
exit()


