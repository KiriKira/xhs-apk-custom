.class public final Lcom/xingin/matrix/setting/SettingActivityV2;
.super Lcom/xingin/android/redutils/base/XhsActivity;
.source "SourceFile"


# annotations
.annotation runtime Lasc/a;
.end annotation


# instance fields
.field private __xst_injected_callback_list:Ljava/lang/Object;


# direct methods
.method public constructor <init>()V
    .locals 0

    .line 1
    invoke-direct {p0}, Lcom/xingin/android/redutils/base/XhsActivity;-><init>()V

    .line 2
    return-void
    .line 5
.end method

.method public static Vd(Lcom/xingin/matrix/setting/SettingActivityV2;Landroid/os/Bundle;)V
    .locals 4

    .line 1
    const/4 v0, 0x0

    .line 2
    invoke-virtual {p0, v0}, Lcom/xingin/android/redutils/base/XhsActivity;->setHandleStatusBar(Z)V

    .line 3
    invoke-super {p0, p1}, Lcom/xingin/android/redutils/base/XhsActivity;->onCreate(Landroid/os/Bundle;)V

    .line 6
    sget-object p1, Lbc2/m;->a:Lbc2/m;

    .line 9
    sget-object v0, Lbc2/r0;->a:Lbc2/r0;

    .line 11
    invoke-virtual {p0}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;

    .line 13
    move-result-object v1

    .line 16
    const-string v2, " "

    .line 17
    if-eqz v1, :cond_0

    .line 19
    invoke-virtual {v1}, Landroid/content/Intent;->getExtras()Landroid/os/Bundle;

    .line 21
    move-result-object v1

    .line 24
    if-eqz v1, :cond_0

    .line 25
    const-string v3, "key_raw_url"

    .line 27
    invoke-virtual {v1, v3}, Landroid/os/BaseBundle;->getString(Ljava/lang/String;)Ljava/lang/String;

    .line 29
    move-result-object v1

    .line 32
    if-nez v1, :cond_1

    .line 33
    :cond_0
    move-object v1, v2

    .line 35
    :cond_1
    invoke-virtual {p0}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;

    .line 36
    move-result-object p0

    .line 39
    if-eqz p0, :cond_3

    .line 40
    const-string v3, "sourceId"

    .line 42
    invoke-virtual {p0, v3}, Landroid/content/Intent;->getStringExtra(Ljava/lang/String;)Ljava/lang/String;

    .line 44
    move-result-object p0

    .line 47
    if-nez p0, :cond_2

    .line 48
    goto :goto_0

    .line 50
    :cond_2
    move-object v2, p0

    .line 51
    :cond_3
    :goto_0
    const-string p0, "DETAIL_PAGE_ARRIVED"

    .line 52
    invoke-virtual {v0, v1, v2, p0}, Lbc2/r0;->f(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Lbc2/q0;

    .line 54
    move-result-object p0

    .line 57
    invoke-virtual {p1, p0}, Lbc2/m;->b(Ljava/lang/Object;)V

    .line 58
    return-void
.end method

.method public static synthetic Wd(Lcom/xingin/matrix/setting/SettingActivityV2;)Ljava/lang/Object;
    .locals 0

    .line 1
    iget-object p0, p0, Lcom/xingin/matrix/setting/SettingActivityV2;->__xst_injected_callback_list:Ljava/lang/Object;

    return-object p0
.end method


# virtual methods
.method public createLinker(Landroid/view/ViewGroup;)Lvl7/s;
    .locals 4
    .param p1    # Landroid/view/ViewGroup;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "Landroid/view/ViewGroup;",
            ")",
            "Lvl7/s<",
            "****>;"
        }
    .end annotation

    .annotation build Lorg/jetbrains/annotations/NotNull;
    .end annotation

    .line 1
    new-instance v0, Lcom/xingin/matrix/setting/c;

    .line 2
    new-instance v1, Lcom/xingin/matrix/setting/SettingActivityV2$a;

    .line 4
    invoke-direct {v1}, Ljava/lang/Object;-><init>()V

    .line 6
    invoke-direct {v0, v1}, Lvl7/q;-><init>(Ljava/lang/Object;)V

    .line 9
    invoke-virtual {p0}, Lcom/xingin/android/redutils/base/XhsActivity;->getSwipeBackHelper()Lcom/xingin/xhstheme/view/swipeback/a;

    .line 12
    move-result-object v1

    .line 15
    if-eqz v1, :cond_0

    .line 16
    iget-object v1, v1, Lcom/xingin/xhstheme/view/swipeback/a;->b:Lcom/xingin/xhstheme/view/swipeback/SwipeBackLayout;

    .line 18
    if-eqz v1, :cond_0

    .line 20
    const/4 v2, 0x1

    .line 22
    invoke-virtual {v1, v2}, Lcom/xingin/xhstheme/view/swipeback/SwipeBackLayout;->setIsSupportFullScreenBack(Z)V

    .line 23
    :cond_0
    invoke-virtual {v0, p1}, Lvl7/q;->createView(Landroid/view/ViewGroup;)Landroid/view/View;

    .line 26
    move-result-object p1

    .line 29
    check-cast p1, Lcom/xingin/matrix/setting/SettingView;

    .line 30
    new-instance v1, Lq0a/k;

    .line 32
    invoke-direct {v1}, Lq0a/k;-><init>()V

    .line 34
    new-instance v2, Lcom/xingin/matrix/setting/a;

    .line 37
    invoke-direct {v2}, Ljava/lang/Object;-><init>()V

    .line 39
    invoke-virtual {v0}, Lvl7/a;->getDependency()Ljava/lang/Object;

    .line 42
    move-result-object v0

    .line 45
    check-cast v0, Lcom/xingin/matrix/setting/c$c;

    .line 46
    invoke-virtual {v0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;

    .line 48
    iput-object v0, v2, Lcom/xingin/matrix/setting/a;->b:Lcom/xingin/matrix/setting/c$c;

    .line 51
    new-instance v0, Lcom/xingin/matrix/setting/c$b;

    .line 53
    invoke-direct {v0, p1, v1, p0}, Lcom/xingin/matrix/setting/c$b;-><init>(Lcom/xingin/matrix/setting/SettingView;Lq0a/k;Lcom/xingin/android/redutils/base/XhsActivity;)V

    .line 55
    iput-object v0, v2, Lcom/xingin/matrix/setting/a;->a:Lcom/xingin/matrix/setting/c$b;

    .line 58
    iget-object v0, v2, Lcom/xingin/matrix/setting/a;->b:Lcom/xingin/matrix/setting/c$c;

    .line 60
    const-class v3, Lcom/xingin/matrix/setting/c$c;

    .line 62
    invoke-static {v0, v3}, Lrvd/c;->a(Ljava/lang/Object;Ljava/lang/Class;)V

    .line 64
    new-instance v0, Lcom/xingin/matrix/setting/b;

    .line 67
    iget-object v2, v2, Lcom/xingin/matrix/setting/a;->a:Lcom/xingin/matrix/setting/c$b;

    .line 69
    invoke-direct {v0}, Ljava/lang/Object;-><init>()V

    .line 71
    new-instance v3, Lcom/xingin/matrix/setting/j;

    .line 74
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/j;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 76
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 79
    move-result-object v3

    .line 82
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->a:Ljavax/inject/Provider;

    .line 83
    new-instance v3, Lcom/xingin/matrix/setting/d;

    .line 85
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/d;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 87
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 90
    move-result-object v3

    .line 93
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->b:Ljavax/inject/Provider;

    .line 94
    new-instance v3, Lcom/xingin/matrix/setting/g;

    .line 96
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/g;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 98
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 101
    move-result-object v3

    .line 104
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->c:Ljavax/inject/Provider;

    .line 105
    new-instance v3, Lcom/xingin/matrix/setting/f;

    .line 107
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/f;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 109
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 112
    move-result-object v3

    .line 115
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->d:Ljavax/inject/Provider;

    .line 116
    new-instance v3, Lcom/xingin/matrix/setting/k;

    .line 118
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/k;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 120
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 123
    move-result-object v3

    .line 126
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->e:Ljavax/inject/Provider;

    .line 127
    new-instance v3, Lcom/xingin/matrix/setting/l;

    .line 129
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/l;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 131
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 134
    move-result-object v3

    .line 137
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->f:Ljavax/inject/Provider;

    .line 138
    new-instance v3, Lcom/xingin/matrix/setting/i;

    .line 140
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/i;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 142
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 145
    move-result-object v3

    .line 148
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->g:Ljavax/inject/Provider;

    .line 149
    new-instance v3, Lcom/xingin/matrix/setting/h;

    .line 151
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/h;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 153
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 156
    move-result-object v3

    .line 159
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->h:Ljavax/inject/Provider;

    .line 160
    new-instance v3, Lcom/xingin/matrix/setting/m;

    .line 162
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/m;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 164
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 167
    move-result-object v3

    .line 170
    iput-object v3, v0, Lcom/xingin/matrix/setting/b;->i:Ljavax/inject/Provider;

    .line 171
    new-instance v3, Lcom/xingin/matrix/setting/e;

    .line 173
    invoke-direct {v3, v2}, Lcom/xingin/matrix/setting/e;-><init>(Lcom/xingin/matrix/setting/c$b;)V

    .line 175
    invoke-static {v3}, Lrvd/a;->a(Ljavax/inject/Provider;)Ljavax/inject/Provider;

    .line 178
    move-result-object v2

    .line 181
    iput-object v2, v0, Lcom/xingin/matrix/setting/b;->j:Ljavax/inject/Provider;

    .line 182
    new-instance v2, Lcom/xingin/matrix/setting/n;

    .line 184
    invoke-direct {v2, p1, v1, v0}, Lcom/xingin/matrix/setting/n;-><init>(Lcom/xingin/matrix/setting/SettingView;Lq0a/k;Lcom/xingin/matrix/setting/c$a;)V

    .line 186
    return-object v2
    .line 189
.end method

.method public onCreate(Landroid/os/Bundle;)V
    .locals 3

    .line 1
    :try_start_0
    invoke-static {p0}, Lcom/xingin/matrix/setting/SettingActivityV2;->Wd(Lcom/xingin/matrix/setting/SettingActivityV2;)Ljava/lang/Object;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 2
    goto :goto_0

    .line 5
    :catchall_0
    move-exception v0

    .line 6
    const-string v1, "LancetHook"

    .line 7
    const-string v2, "Error in activity onCreate hook"

    .line 9
    invoke-static {v1, v2, v0}, Ls2c/d;->f(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)V

    .line 11
    :goto_0
    invoke-static {p0, p1}, Lcom/xingin/matrix/setting/SettingActivityV2;->Vd(Lcom/xingin/matrix/setting/SettingActivityV2;Landroid/os/Bundle;)V

    .line 14
    return-void
    .line 17
.end method

.method public onSkinChange(Lzld/d;II)V
    .locals 0
    .param p1    # Lzld/d;
        .annotation build Lorg/jetbrains/annotations/Nullable;
        .end annotation
    .end param

    .line 1
    invoke-super {p0, p1, p2, p3}, Lcom/xingin/android/redutils/base/XhsActivity;->onSkinChange(Lzld/d;II)V

    .line 2
    sget-object p1, Ln92/n3;->a:Ln92/n3;

    .line 5
    invoke-virtual {p1, p0}, Ln92/n3;->a(Landroid/app/Activity;)V

    .line 7
    sget-object p1, Ln92/e2;->a:Ln92/e2;

    .line 10
    const p2, 0x7f06118e    # @color/xhsTheme_colorGrayLevel7 '#fafafa'

    .line 12
    invoke-static {p2}, Lgmd/c;->f(I)I

    .line 15
    move-result p2

    .line 18
    invoke-virtual {p1, p0, p2}, Ln92/e2;->d(Landroid/app/Activity;I)V

    .line 19
    return-void
    .line 22
.end method

.method public onStop()V
    .locals 1

    .line 1
    invoke-super {p0}, Lcom/xingin/android/redutils/base/XhsActivity;->onStop()V

    .line 2
    sget-object v0, Lbc2/o;->a:Lbc2/o;

    .line 5
    invoke-virtual {v0}, Lbc2/o;->d()V

    .line 7
    return-void
    .line 10
.end method

.method public onUserInteraction()V
    .locals 0

    invoke-static {}, Lxgd/e0;->c()V

    invoke-super {p0}, Lcom/xingin/android/redutils/base/XhsActivity;->onUserInteraction()V

    return-void
.end method

.method public onWindowFocusChanged(Z)V
    .locals 5

    .line 1
    invoke-super {p0, p1}, Lcom/xingin/foundation/framework/v2/LCBActivity;->onWindowFocusChanged(Z)V

    .line 2
    if-eqz p1, :cond_4

    .line 5
    sget-object p1, Lbc2/m;->a:Lbc2/m;

    .line 7
    sget-object v0, Lbc2/r0;->a:Lbc2/r0;

    .line 9
    invoke-virtual {p0}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;

    .line 11
    move-result-object v1

    .line 14
    const-string v2, " "

    .line 15
    if-eqz v1, :cond_0

    .line 17
    invoke-virtual {v1}, Landroid/content/Intent;->getExtras()Landroid/os/Bundle;

    .line 19
    move-result-object v1

    .line 22
    if-eqz v1, :cond_0

    .line 23
    const-string v3, "key_raw_url"

    .line 25
    invoke-virtual {v1, v3}, Landroid/os/BaseBundle;->getString(Ljava/lang/String;)Ljava/lang/String;

    .line 27
    move-result-object v1

    .line 30
    if-nez v1, :cond_1

    .line 31
    :cond_0
    move-object v1, v2

    .line 33
    :cond_1
    invoke-virtual {p0}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;

    .line 34
    move-result-object v3

    .line 37
    if-eqz v3, :cond_3

    .line 38
    const-string v4, "sourceId"

    .line 40
    invoke-virtual {v3, v4}, Landroid/content/Intent;->getStringExtra(Ljava/lang/String;)Ljava/lang/String;

    .line 42
    move-result-object v3

    .line 45
    if-nez v3, :cond_2

    .line 46
    goto :goto_0

    .line 48
    :cond_2
    move-object v2, v3

    .line 49
    :cond_3
    :goto_0
    const-string v3, "NOTE_DETAIL_EXPOSE"

    .line 50
    invoke-virtual {v0, v1, v2, v3}, Lbc2/r0;->f(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Lbc2/q0;

    .line 52
    move-result-object v0

    .line 55
    invoke-virtual {p1, v0}, Lbc2/m;->b(Ljava/lang/Object;)V

    .line 56
    :cond_4
    return-void
    .line 59
.end method
