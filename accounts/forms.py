from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class RegistrationForm(forms.ModelForm):
    """自助注册:提交后账号处于「待核准」(is_active=False),由管理员激活。"""

    display_name = forms.CharField(
        label="姓名 / 昵称", required=False, max_length=50,
    )
    email = forms.EmailField(label="邮箱（可选）", required=False)
    password = forms.CharField(
        label="密码（至少 8 位）", min_length=8, widget=forms.PasswordInput,
    )

    class Meta:
        model = User
        fields = ["username"]

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("该用户名已被使用,请换一个。")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            probe = User(username=cleaned.get("username") or "",
                         email=cleaned.get("email") or "")
            try:
                validate_password(password, probe)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.email = self.cleaned_data.get("email", "")
        user.role = User.Role.EXPERT      # 自助注册默认为协作专家
        user.is_active = False            # 待管理员核准后方可登录
        if self.cleaned_data.get("display_name"):
            user.first_name = self.cleaned_data["display_name"]
        if commit:
            user.save()
        return user
