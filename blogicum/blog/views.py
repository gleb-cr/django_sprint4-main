from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.aggregates import Count
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, DeleteView, UpdateView

from .forms import PostForm, CommentForm
from .models import Post, Category, Comment


class IndexListView(ListView):
    model = Post
    queryset = Post.objects.select_related(
        'category',
        'author',
        'location',
    ).annotate(
        comment_count=Count('comments')
    ).filter(
        is_published=True,
        pub_date__lte=timezone.now(),
        category__is_published=True,
    )
    template_name = 'blog/index.html'
    ordering = '-pub_date'
    paginate_by = 10


def profile_detail(request, username):
    template = "blog/profile.html"
    profile = get_object_or_404(
        User.objects.all(
        ).filter(
            username=username
        )
    )
    posts = Post.objects.filter(author__username=username).order_by('-pub_date').annotate(
        comment_count=Count('comments'))
    if request.user != profile:
        posts = posts.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'profile': profile,
        'page_obj': page_obj,
    }
    return render(request, template, context)


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = User
    template_name = 'blog/user.html'
    fields = ('username', 'first_name', 'last_name', 'email')

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse_lazy('blog:profile', kwargs={'username': self.request.user.username})


def post_detail(request, post_id):
    template = "blog/detail.html"

    post_qs = Post.objects.select_related(
        'category',
        'author',
        'location',
    )
    if request.user.is_authenticated:
        post_qs = post_qs.filter(
            Q(author=request.user)
            | (Q(is_published=True)
               & Q(pub_date__lte=timezone.now())
               & Q(category__is_published=True))
        )
    else:
        post_qs = post_qs.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
    post = get_object_or_404(post_qs.filter(id=post_id))

    comments = post.comments.select_related(
        'author',
    ).order_by('created_at')
    form = CommentForm()

    context = {
        "post": post,
        "form": form,
        "comments": comments
    }
    return render(request, template, context)


def category_posts(request, category_slug):
    template = "blog/category.html"
    post_list = Post.objects.select_related(
        'category',
        'author',
        'location',
    ).annotate(
        comment_count=Count('comments')
    ).filter(
        is_published=True,
        pub_date__lte=timezone.now(),
        category__slug=category_slug,
        category__is_published=True,
    ).order_by('-pub_date')
    category = get_object_or_404(
        Category.objects.all().filter(
            slug=category_slug,
            is_published=True,
        )
    )
    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        "category": category,
        "page_obj": page_obj,
    }
    return render(request, template, context)


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('blog:profile', kwargs={'username': self.request.user.username})


class PostEditView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html'

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=self.kwargs.get('post_id'))
        if post.author != request.user:
            return redirect('blog:post_detail', post_id=self.kwargs.get('post_id'))
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return get_object_or_404(Post, pk=self.kwargs.get('post_id'))

    def get_success_url(self):
        return reverse_lazy('blog:post_detail', kwargs={'post_id': self.object.id})


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/post_form.html'

    def get_queryset(self):
        return Post.objects.filter(author=self.request.user)

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get('post_id'))

    def get_success_url(self):
        return reverse_lazy('blog:profile', kwargs={'username': self.request.user.username})


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(
        Post,
        pk=post_id,
        is_published=True,
        pub_date__lte=timezone.now(),
        category__is_published=True,
    )
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', post_id=post_id)


class CommentEditView(LoginRequiredMixin, UpdateView):
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'

    def get_queryset(self):
        return Comment.objects.filter(author=self.request.user)

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset(),
            pk=self.kwargs.get('comment_id'),
            post_id=self.kwargs.get('post_id'),
        )

    def get_success_url(self):
        return reverse_lazy('blog:post_detail', kwargs={'post_id': self.object.post_id})


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment
    template_name = 'blog/comment.html'

    def get_queryset(self):
        return Comment.objects.filter(author=self.request.user)

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset(),
            pk=self.kwargs.get('comment_id'),
            post_id=self.kwargs.get('post_id'),
        )

    def get_success_url(self):
        return reverse_lazy('blog:post_detail', kwargs={'post_id': self.kwargs.get('post_id')})
