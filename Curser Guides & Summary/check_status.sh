#!/bin/bash
# Quick status check - run from ds-experiment-omri directory
# Usage: bash check_status.sh

cd ~/ds-experiment-omri
source venv/bin/activate

python manage.py shell << 'PYEOF'
from experiment.models import ExperimentData, ExperimentAction, TOASTResponse

print("=" * 60)
print("QUICK STATUS CHECK")
print("=" * 60)

total_users = ExperimentData.objects.count()
completed = ExperimentData.objects.filter(complete=True).count()
incomplete = total_users - completed
total_actions = ExperimentAction.objects.count()
total_toast = TOASTResponse.objects.count()

print(f"\n📊 Participants:")
print(f"   Total: {total_users}")
print(f"   ✅ Completed: {completed}")
print(f"   ❌ Incomplete: {incomplete}")
print(f"   📝 Total Actions: {total_actions}")
print(f"   📋 TOAST Responses: {total_toast}")

print(f"\n📈 Recent Users (last 5):")
for u in ExperimentData.objects.order_by('-start_time')[:5]:
    actions = ExperimentAction.objects.filter(user_id=u.user_id).count()
    toast = "✅" if TOASTResponse.objects.filter(user_id=u.user_id).exists() else "❌"
    status = "✅ COMPLETE" if u.complete else "❌ INCOMPLETE"
    print(f"   User {u.user_id}: {actions}/120 actions, TOAST: {toast}, {status}")

print("\n" + "=" * 60)
exit()
PYEOF


