"""
Check details of User 81's duplicate TOAST responses
Run: python manage.py shell < check_user81_details.py
"""

from experiment.models import ExperimentData, ExperimentAction, TOASTResponse
from django.utils import timezone

print("=" * 60)
print("DETAILED CHECK: User 81 - Multiple TOAST Responses")
print("=" * 60)

user = ExperimentData.objects.get(user_id=81)
print(f"\nUser 81 Info:")
print(f"   AID: {user.aid}")
print(f"   Complete: {user.complete}")
print(f"   Start Time: {user.start_time}")
print(f"   End Time: {user.end_time}")
print(f"   Actions: {ExperimentAction.objects.filter(user_id=81).count()}/120")

toast_responses = TOASTResponse.objects.filter(user_id=81).order_by('id')
print(f"\n📋 TOAST Responses ({toast_responses.count()} total):")
print("=" * 60)

for i, toast in enumerate(toast_responses, 1):
    print(f"\nTOAST Response #{i} (ID: {toast.id}):")
    print(f"   Usefulness: {toast.usefulness}")
    print(f"   Reliability: {toast.reliability}")
    print(f"   Trust: {toast.trust}")
    print(f"   Age Group: {toast.age_group}")
    print(f"   Gender: {toast.gender}")
    print(f"   Education: {toast.education}")
    
    # Check if all values are the same
    if i > 1:
        prev_toast = toast_responses[i-2]
        same = (
            toast.usefulness == prev_toast.usefulness and
            toast.reliability == prev_toast.reliability and
            toast.trust == prev_toast.trust and
            toast.age_group == prev_toast.age_group and
            toast.gender == prev_toast.gender and
            toast.education == prev_toast.education
        )
        print(f"   Same as previous: {'✅ YES' if same else '❌ NO (different answers!)'}")

print("\n" + "=" * 60)
print("RECOMMENDATION:")
print("=" * 60)
print("Keep only the FIRST response (ID: 47)")
print("Delete the duplicates (IDs: 49, 50)")
print("=" * 60)
exit()


