from django import forms

from .models import (
    Category, Department, Employee, HardwareNode, InventoryItem,
    PurchaseRequest, Resource, Supplier,
)


class StyledForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")


class ResourceForm(StyledForm):
    class Meta:
        model = Resource
        fields = "__all__"
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class CategoryForm(StyledForm):
    class Meta:
        model = Category
        fields = "__all__"


class InventoryItemForm(StyledForm):
    class Meta:
        model = InventoryItem
        fields = "__all__"
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class SupplierForm(StyledForm):
    class Meta:
        model = Supplier
        fields = "__all__"
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class DepartmentForm(StyledForm):
    class Meta:
        model = Department
        fields = "__all__"
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class EmployeeForm(StyledForm):
    class Meta:
        model = Employee
        fields = "__all__"
        widgets = {"date_hired": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class PurchaseRequestForm(StyledForm):
    class Meta:
        model = PurchaseRequest
        fields = ["item", "supplier", "quantity"]  # status changes via approve/receive actions


class HardwareNodeForm(StyledForm):
    class Meta:
        model = HardwareNode
        exclude = ["last_seen"]


class AssignmentForm(forms.Form):
    item = forms.ModelChoiceField(queryset=InventoryItem.objects.none())
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    quantity = forms.IntegerField(min_value=1, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = InventoryItem.objects.filter(quantity__gt=0)
        self.fields["item"].label_from_instance = lambda i: f"{i.name} ({i.sku}) - {i.quantity} in stock"
        self.fields["employee"].queryset = Employee.objects.filter(is_active=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        data = super().clean()
        item, qty = data.get("item"), data.get("quantity")
        if item and qty and qty > item.quantity:
            self.add_error("quantity", f"Only {item.quantity} available in stock.")
        return data
